from server.market.baseExchange import *
from server.market import kPm
kMaxLimit = 1000
kMarket, kLimit = 'Market', 'Limit'
kLinear, kInverse, kOption = 'linear', 'inverse', 'option'
CATEGORY_MAP = {'spot': 'spot', 'swap': kLinear}
POS_IDX = {kLong: 1, kShort: 2}   # 双向持仓 positionIdx
kLeverageNotModified = 110043     # 杠杆未变化,视为成功


def _num(value) -> float:
    """交易所常返回空字符串,统一转 float"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class bybit(baseExchange):
    """Bybit 交易所实现: 统一账户(UTA) + U本位合约(双向持仓)"""
    _name = "bybit"

    def __init__(self, description: str):
        super().__init__(description, kMaxLimit)
        self._defaultLv: dict[str, int] = {}  # {symbol_id: leverage}

    def _create(self, config: dict) -> None:
        super()._create(config)
        api = self._info['api']
        self._ccxt = ccxt.bybit({
            'apiKey': api['apiKey'],
            'secret': api['secret'],
            'timeout': 30000,
            'enableRateLimit': True,
            'options': {'defaultType': kSpot},
        })

        def _wsCreate(defaultType: str):
            return ccxtpro.bybit({
                'apiKey': api['apiKey'],
                'secret': api['secret'],
                'enableRateLimit': True,
                'timeout': 30000,
                'options': {'defaultType': defaultType},
            })
        self._wsSpot = _wsCreate('spot')
        self._wsSwap = _wsCreate('swap')

    def _getCategory(self, symbol: str) -> tuple[str, str]:
        """从 symbol 解析 (category, newSymbol)"""
        type_, newSymbol = slit(symbol, '_')
        return CATEGORY_MAP.get(type_, type_), newSymbol

    def _rtParams(self, symbol: str, limit: int = 0) -> dict:
        """构建通用请求参数"""
        category, newSymbol = self._getCategory(symbol)
        params = {'category': category, 'symbol': newSymbol}
        if limit > 0:
            params['limit'] = limit
        return params

    # ── 账户 ──
    def balance(self, isSpot=True) -> dict:
        super().balance(isSpot)
        rt = self._ccxt.privateGetV5AccountWalletBalance(params={'accountType': 'UNIFIED'})
        wallet = rt['result']['list'][0]
        # 返回格式:{'total':{},'free':{},kPm:{}}
        self._acc[kPm] = {
            'equity': _num(wallet.get('totalEquity')),
            'free': _num(wallet.get('totalAvailableBalance')),
            'uniMMR': _num(wallet.get('accountMMRate')),
            'danger': _num(wallet.get('totalMaintenanceMargin')),
            'total': {c['coin']: bal for c in wallet.get('coin', [])
                      if (bal := _num(c.get('walletBalance'))) != 0},
        }
        return self._acc

    def accFree(self, coin: str = '', isPm: bool = False):
        if isPm:
            return self._acc[kPm].get('free')  # 统一账户可用金额
        return super().accFree(coin)

    def _orderParams(self, category: str) -> dict:
        return {} if category == kSpot else {'category': kLinear}

    def _spotBuyQuoteParams(self, totelPrice) -> dict:
        return {'cost': totelPrice}

    # ── 订单/持仓查询 ──
    def findOrder(self, symbol: str, orderId: str | int = '', isPos=True, isOpen=False):
        sid, category, symbolInfo = '', '', {}
        if symbol:
            category, symbolInfo = self.coinInfo(symbol)
            sid = symbolInfo.get('id')
        targetId = str(orderId) if str(orderId) not in ('', '-1') else ''
        if category == kSpot:
            orders = self._ccxt.fetch_open_orders(symbolInfo['symbol'])
            return [o for o in orders if not targetId or str(o.get('id')) == targetId]

        def _openOrders() -> list[dict]:
            params = {'category': kLinear, 'limit': 50}
            params.update(symbol=sid) if sid else params.update(settleCoin='USDT')
            if targetId:
                params['orderId'] = targetId
            rt = self._ccxt.privateGetV5OrderRealtime(params=params)
            return [{**o, 'id': o['orderId'], 'clientOrderId': o.get('orderLinkId'),
                     'amount': _num(o.get('qty')), 'filled': _num(o.get('cumExecQty')),
                     'remaining': max(_num(o.get('qty')) - _num(o.get('cumExecQty')), 0.0)}
                    for o in rt['result']['list']]

        def _positions() -> list[dict]:
            params = {'category': kLinear}
            params.update(symbol=sid) if sid else params.update(settleCoin='USDT')
            rt = self._ccxt.privateGetV5PositionList(params=params)
            return [{'symbol': p['symbol'],
                     'dir': (kBuy if p['side'] == 'Buy' else kSell) + '_' + (kLong if p['positionIdx'] == 1 else kShort),
                     'side': kLong if p['positionIdx'] == 1 else kShort,
                     'open': p['avgPrice'],
                     'lv': p['leverage'],
                     'unRealized': p['unrealisedPnl'],
                     'amount': _num(p['size'])}
                    for p in rt['result']['list'] if _num(p.get('size')) != 0]

        open_orders = _openOrders() if isOpen else []
        if not isPos:
            return open_orders
        return open_orders, _positions()

    # ── 合约下单 ──
    def _contractOrder(self, state: str, symbol: dict, amount: float, isMarket: bool, inForce: str, price: float | None = None, lv: int = 1, posSide: str | None = None, clientOrderId: str | None = None):
        _, symbolInfo = self.coinInfo(symbol)
        sid = symbolInfo.get('id')
        if self._defaultLv.get(sid) != lv:
            self._setLeverage(kLinear, sid, lv)
            self._defaultLv[sid] = lv
        params = {
            'category': kLinear,
            'symbol': sid,
            'side': state.capitalize(),
            'orderType': kMarket if isMarket else kLimit,
            'qty': str(amount),
            'positionIdx': POS_IDX.get(posSide, 0)}
        if isMarket:
            params['timeInForce'] = 'IOC'
        else:
            params['price'] = str(price)
            params['timeInForce'] = inForce
        if clientOrderId:
            params['orderLinkId'] = clientOrderId
        return self._check(self._ccxt.privatePostV5OrderCreate(params=params), 'order')

    # ── 合约撤单 ──
    def _cancelOrder(self, symbol: str, id: str):
        _, symbolInfo = self.coinInfo(symbol)
        params = {'category': kLinear, 'symbol': symbolInfo.get('id')}
        if not id:
            return self._check(self._ccxt.privatePostV5OrderCancelAll(params=params), 'cancelAll')
        params['orderId'] = id
        return self._check(self._ccxt.privatePostV5OrderCancel(params=params), 'cancel')

    def _check(self, rt: dict, action: str) -> dict:
        """retCode != 0 视为业务错误,抛出交由上层回滚"""
        if rt.get('retCode') != 0:
            raise ccxt.ExchangeError(f"bybit {action} error: {rt}")
        return rt

    # ── 批量下单 ──
    def _batchOrders(self, category: str, orders: list[dict]):
        """批量下单,交易所上限10单(基类先限5单)"""
        requestList = []
        for order in orders:
            isLimit = order.get('price') is not None
            item = {
                'symbol': order['symbol'],
                'side': order['side'].capitalize(),
                'orderType': kLimit if isLimit else kMarket,
                'qty': str(order['amount']),
                'positionIdx': POS_IDX.get(order.get('posSide'), 0)
            }
            if isLimit:
                item['price'] = str(order['price'])
                item['timeInForce'] = order.get('timeInForce', 'GTC')
            else:
                item['timeInForce'] = 'IOC'
            requestList.append(item)
        params = {'category': kLinear, 'request': requestList}
        rt = tryCatch(lambda: self._ccxt.privatePostV5OrderCreateBatch(params=params))
        if not rt or rt.get('retCode') != 0:
            err("bybit batchOrders error:", rt)
            return None
        return rt.get('result', {}).get('list', [])

    def _setLeverage(self, category: str, symbol: str, leverage: int):
        """内部设置杠杆,杠杆未变化时交易所返回110043,视为成功"""
        params = {
            'category': category,
            'symbol': symbol,
            'buyLeverage': str(leverage),
            'sellLeverage': str(leverage)
        }
        try:
            return self._ccxt.privatePostV5PositionSetLeverage(params=params)
        except ccxt.ExchangeError as e:
            if str(kLeverageNotModified) not in str(e):
                raise

    def setLeverage(self, symbol: str, leverage: int, category: str = kLinear):
        """设置杠杆"""
        _, newSymbol = self._getCategory(symbol)
        return self._setLeverage(category, newSymbol, leverage)

    def setPositionMode(self, mode: str = 'BothSide', category: str = kLinear, symbol: str | None = None):
        """设置持仓模式 mode: 'BothSide'(双向) / 'MergedSingle'(单向)"""
        params = {'category': category, 'mode': mode}
        if symbol:
            params['symbol'] = symbol
        return tryCatch(lambda: self._ccxt.privatePostV5PositionSwitchMode(params=params))

    def setMarginMode(self, marginMode: str = 'REGULAR_MARGIN'):
        """设置保证金模式 marginMode: 'REGULAR_MARGIN'(普通) / 'PORTFOLIO_MARGIN'(组合保证金)"""
        return tryCatch(lambda: self._ccxt.privatePostV5AccountSetMarginMode(params={'setMarginMode': marginMode}))

    # ── K线 ──
    @staticmethod
    def _interval(timeframe: str) -> str:
        """1m→'1', 1h→'60', 1d→'D', 1w→'W'"""
        n, unit = int(timeframe[:-1]), timeframe[-1]
        return {'m': str(n), 'h': str(n * 60), 'd': 'D', 'w': 'W'}[unit]

    def _marketKline(self, symbol: str, beginTime: int | None, endTime: int | None,
                     timeframe: str = '5m', limit: int = 0) -> pd.DataFrame | None:
        """获取 K 线。交易所倒序返回最新 limit 条,给定区间时从 end 向前回溯拼接到 begin"""
        category, newSymbol = self._getCategory(symbol)
        effectiveLimit = limit if limit > 0 else self._maxLimit
        params = {'category': category, 'symbol': newSymbol,
                  'interval': self._interval(timeframe), 'limit': effectiveLimit}
        if beginTime is not None:
            params['start'] = beginTime
        if endTime is not None:
            params['end'] = endTime
        rows: dict[str, list] = {}
        while True:
            rt = tryCatch(lambda: self._ccxt.publicGetV5MarketKline(params))
            page = (rt or {}).get('result', {}).get('list') or []
            if not page:
                break
            rows.update({r[0]: r for r in page})
            oldest = int(page[-1][0])
            if beginTime is None or endTime is None or oldest <= beginTime or len(page) < effectiveLimit:
                break
            params['end'] = oldest - 1
        if not rows:
            return None
        kline = pdData()
        kline.format(list(rows.values()), style='candle')
        return kline.raw()

    # ── 行情 ──
    def depth(self, symbol: str, limit: int):
        """深度数据"""
        params = self._rtParams(symbol, limit)
        rt = tryCatch(lambda: self._ccxt.publicGetV5MarketOrderbook(params))
        if not rt or not rt.get('result'):
            return None

        data = rt['result']
        return {'bids': data['b'], 'asks': data['a'], 'T': data.get('ts')}

    def orderBook(self, symbol: str, limit: int = 5):
        _, symbolInfo = self.coinInfo(symbol)
        return self._ccxt.fetch_order_book(symbol=symbolInfo.get('symbol'), limit=limit)

    def trades(self, symbol: str, limit: int) -> list:
        """成交历史"""
        params = self._rtParams(symbol, limit)
        rt = tryCatch(lambda: self._ccxt.publicGetV5MarketRecentTrade(params))
        if not rt or not rt.get('result', {}).get('list'):
            return []

        return [
            {
                'price': trade['price'],
                'qty': trade['size'],
                'quoteQty': float(trade['price']) * float(trade['size']),
                'isBuyerMaker': trade['side'] == 'Buy',
                'time': trade.get('time')
            }
            for trade in rt['result']['list']
        ]

    def tickers(self, symbol: str):
        """最新币价"""
        params = self._rtParams(symbol)
        rt = tryCatch(lambda: self._ccxt.publicGetV5MarketTickers(params))
        if not rt or not rt.get('result', {}).get('list'):
            return None

        data = rt['result']['list'][0]
        data['price'] = data.get('lastPrice')
        return data

    def bookTickers(self, symbol: str):
        """最优价"""
        params = self._rtParams(symbol)
        rt = tryCatch(lambda: self._ccxt.publicGetV5MarketTickers(params))
        if not rt or not rt.get('result', {}).get('list'):
            return None

        data = rt['result']['list'][0]
        return {
            'symbol': data.get('symbol'),
            'bidPrice': data.get('bid1Price'),
            'bidQty': data.get('bid1Size'),
            'askPrice': data.get('ask1Price'),
            'askQty': data.get('ask1Size')
        }

    def fundingRate(self, symbol: str, category: str = kLinear):
        """资金费率"""
        _, newSymbol = self._getCategory(symbol)
        params = {'category': category, 'symbol': newSymbol}

        rt = tryCatch(lambda: self._ccxt.publicGetV5MarketFundingHistory(params=params))
        if not rt or not rt.get('result', {}).get('list'):
            return None
        return rt['result']['list']

    def optionOrder(self, state: str, **kwargs):
        """期权下单 state: 'buy'/'sell'/'cancel'"""
        params = {'category': kOption, 'symbol': kwargs['symbol']}

        if state in (kBuy, kSell):
            isLimit = kwargs.get('price') is not None
            params.update({
                'side': state.capitalize(),
                'orderType': kLimit if isLimit else kMarket,
                'qty': str(kwargs['amount'])
            })
            if isLimit:
                params['price'] = str(kwargs['price'])
                params['timeInForce'] = kwargs.get('timeInForce', 'GTC')
        elif state == 'cancel':
            params['orderId'] = kwargs['orderId']

        return tryCatch(lambda: switchFn({
            kBuy: self._ccxt.privatePostV5OrderCreate,
            kSell: self._ccxt.privatePostV5OrderCreate,
            'cancel': self._ccxt.privatePostV5OrderCancel
        }, key=state, params=params))

    def optionFind(self, symbol: str, orderId: str | None = None, limit: int = 1):
        """查询期权订单"""
        params = {'category': kOption, 'symbol': symbol, 'limit': limit}
        if orderId:
            params['orderId'] = orderId
        return tryCatch(lambda: self._ccxt.privateGetV5OrderHistory(params=params))

    # ── ws监听 ──
    def _wsListen(self) -> list[tuple]:
        return [(self._wsSpot, 'SPOT'),
                (self._wsSwap, 'LINEAR')]
