from server.market.baseExchange import *
from server.market import kPm
kMaxLimit = 100  # 最大k线数据
kBatchMax = 20   # 批量下单/撤单上限
kOrdType = {'GTC': 'limit', 'IOC': 'ioc', 'FOK': 'fok', 'GTX': 'post_only'}


def _num(value) -> float:
    """交易所常返回空字符串,统一转 float"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class okx(baseExchange):
    """OKX 交易所实现: 交易账户(全仓) + 永续合约(双向持仓 long_short_mode)
    合约下单量 sz 是"张",对外统一换算成币数(与 binance 一致): 币数 = 张数 * ctVal"""
    _name = "okx"

    def __init__(self, description: str):
        super().__init__(description, kMaxLimit)
        self._defaultLv: dict[str, int] = {}  # {instId: leverage}

    def _create(self, config: dict) -> None:
        super()._create(config)
        api = self._info['api']

        def _options(cls):
            return cls({'apiKey': api['apiKey'],
                        'secret': api['secret'],
                        'password': config['passphrase'],
                        'timeout': 30000,
                        'enableRateLimit': True})
        self._ccxt = _options(ccxt.okx)
        self._wsSpot = _options(ccxtpro.okx)
        self._wsSpot.options['defaultType'] = 'spot'
        self._wsSwap = _options(ccxtpro.okx)
        self._wsSwap.options['defaultType'] = 'swap'

    def _ctVal(self, instId: str) -> float:
        """1张合约对应的币数,现货为1"""
        market = self._ccxt.markets_by_id.get(instId, [{}])[0]
        return float(market.get('contractSize') or 1)

    def _check(self, rt: dict, action: str) -> dict:
        """code/sCode != 0 视为业务错误,抛出交由上层回滚"""
        items = rt.get('data') or [{}]
        if rt.get('code') != '0' or any(i.get('sCode', '0') != '0' for i in items):
            raise ccxt.ExchangeError(f"okx {action} error: {rt}")
        return rt

    # ── 账户 ──
    def balance(self, isSpot=True) -> dict:
        super().balance(isSpot)
        data = self._ccxt.privateGetAccountBalance()['data'][0]
        details = data.get('details', [])
        usdt = next((d for d in details if d.get('ccy') == 'USDT'), {})
        # 返回格式:{'total':{},'free':{},kPm:{}}
        self._acc[kPm] = {
            'equity': _num(data.get('totalEq')),
            'free': _num(data.get('availEq') or usdt.get('availEq')),
            'uniMMR': _num(data.get('mgnRatio')),
            'danger': _num(data.get('mmr')),
            'total': {d['ccy']: eq for d in details if (eq := _num(d.get('eq'))) != 0},
        }
        return self._acc

    def accFree(self, coin: str = '', isPm: bool = False):
        if isPm:
            return self._acc[kPm].get('free')  # 交易账户可用金额
        return super().accFree(coin)

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
            params = {'instType': 'SWAP'}
            if sid:
                params['instId'] = sid
            rows = self._ccxt.privateGetTradeOrdersPending(params=params)['data']
            rows = [o for o in rows if not targetId or o['ordId'] == targetId]
            res = []
            for o in rows:
                ct = self._ctVal(o['instId'])
                amount, filled = _num(o['sz']) * ct, _num(o.get('accFillSz')) * ct
                res.append({**o, 'id': o['ordId'], 'clientOrderId': o.get('clOrdId'),
                            'amount': amount, 'filled': filled,
                            'remaining': max(amount - filled, 0.0)})
            return res

        def _positions() -> list[dict]:
            params = {'instType': 'SWAP'}
            if sid:
                params['instId'] = sid
            rows = self._ccxt.privateGetAccountPositions(params=params)['data']
            return [{'symbol': p['instId'],
                     'dir': (kBuy if p['posSide'] == 'long' else kSell) + '_' + p['posSide'].upper(),
                     'side': p['posSide'].upper(),
                     'open': p['avgPx'],
                     'lv': p['lever'],
                     'unRealized': p['upl'],
                     'amount': abs(_num(p['pos'])) * self._ctVal(p['instId'])}
                    for p in rows if _num(p.get('pos')) != 0]

        open_orders = _openOrders() if isOpen else []
        if not isPos:
            return open_orders
        return open_orders, _positions()

    # ── 合约下单 ──
    def _sz(self, instId: str, amount: float) -> str:
        """币数 → 张数,按交易所精度截断避免浮点噪声"""
        market = self._ccxt.markets_by_id[instId][0]
        return self._ccxt.amount_to_precision(market['symbol'], amount / self._ctVal(instId))

    def _orderItem(self, instId: str, state: str, amount: float, isMarket: bool, inForce: str,
                   price: float | None, posSide: str | None, clientOrderId: str | None) -> dict:
        item = {'instId': instId,
                'tdMode': 'cross',
                'side': state,
                'posSide': (posSide or '').lower(),
                'ordType': 'market' if isMarket else kOrdType.get(inForce, 'limit'),
                'sz': self._sz(instId, amount)}
        if not isMarket:
            item['px'] = str(price)
        if clientOrderId:
            item['clOrdId'] = clientOrderId
        return item

    def _contractOrder(self, state: str, symbol: dict, amount: float, isMarket: bool, inForce: str, price: float | None = None, lv: int = 1, posSide: str | None = None, clientOrderId: str | None = None):
        _, symbolInfo = self.coinInfo(symbol)
        sid = symbolInfo.get('id')
        if self._defaultLv.get(sid) != lv:
            self._check(self._ccxt.privatePostAccountSetLeverage(
                params={'instId': sid, 'lever': str(lv), 'mgnMode': 'cross'}), 'setLeverage')
            self._defaultLv[sid] = lv
        item = self._orderItem(sid, state, amount, isMarket, inForce, price, posSide, clientOrderId)
        return self._check(self._ccxt.privatePostTradeOrder(params=item), 'order')

    # ── 合约撤单 ──
    def _cancelOrder(self, symbol: str, id: str):
        _, symbolInfo = self.coinInfo(symbol)
        sid = symbolInfo.get('id')
        if id:
            return self._check(self._ccxt.privatePostTradeCancelOrder(
                params={'instId': sid, 'ordId': id}), 'cancel')
        pending = self._ccxt.privateGetTradeOrdersPending(params={'instType': 'SWAP', 'instId': sid})['data']
        ids = [{'instId': sid, 'ordId': o['ordId']} for o in pending]
        return [self._check(self._ccxt.privatePostTradeCancelBatchOrders(params=ids[i:i + kBatchMax]), 'cancelAll')
                for i in range(0, len(ids), kBatchMax)]

    # ── 批量下单 ──
    def _batchOrders(self, category: str, orders: list[dict]):
        """批量下单,order['symbol'] 为 instId"""
        items = [self._orderItem(o['symbol'], o['side'], o['amount'], o.get('price') is None,
                                 o.get('timeInForce', 'GTC'), o.get('price'), o.get('posSide'),
                                 o.get('clientOrderId'))
                 for o in orders]
        return tryCatch(lambda: self._check(self._ccxt.privatePostTradeBatchOrders(params=items), 'batchOrders'))

    # ── K线 ──
    @staticmethod
    def _bar(timeframe: str) -> str:
        """1m→'1m', 1h→'1H', 1d→'1Dutc', 1w→'1Wutc'"""
        n, unit = timeframe[:-1], timeframe[-1]
        return n + {'m': 'm', 'h': 'H', 'd': 'Dutc', 'w': 'Wutc'}[unit]

    # spot现货，swap永续              symbol:BTC-USDT / BTC-USDT-SWAP
    def _marketKline(self, symbol: str, beginTime: int | None, endTime: int | None,
                     timeframe: str = '5m', limit: int = 0) -> pd.DataFrame | None:
        """交易所倒序返回,after=早于该时间戳。给定区间时从 end 向前回溯拼接到 begin"""
        category, newSymbol = slit(symbol, '_')
        if category not in (kSpot, kSwap):
            raise ValueError(f"未知的交易品种类型: {category!r} (symbol={symbol!r})")
        effectiveLimit = limit or self._maxLimit
        params = {'instId': newSymbol, 'bar': self._bar(timeframe), 'limit': effectiveLimit}
        if endTime is not None:
            params['after'] = str(endTime + 1)
        elif beginTime is not None:
            params['before'] = str(max(beginTime - 1, 0))
        rows: dict[str, list] = {}
        while True:
            page = self._ccxt.publicGetMarketHistoryCandles(params=params).get('data') or []
            if not page:
                break
            rows.update({r[0]: r for r in page})
            oldest = int(page[-1][0])
            if beginTime is None or endTime is None or oldest <= beginTime or len(page) < effectiveLimit:
                break
            params['after'] = str(oldest)
        if not rows:
            return None
        pdata = pdData()
        pdata.format(list(rows.values()), style='candle')
        return pdata.raw()

    # ── 行情 ──
    def _instId(self, symbol: str) -> str:
        return slit(symbol, '_')[1]

    def depth(self, symbol: str, limit: int):
        """深度数据,归一为 bids/asks=[[价,量]]"""
        params = {'instId': self._instId(symbol), 'sz': limit}
        rt = tryCatch(lambda: self._ccxt.publicGetMarketBooks(params=params))
        if not rt or not rt.get('data'):
            return None
        data = rt['data'][0]
        return {'bids': [l[:2] for l in data['bids']], 'asks': [l[:2] for l in data['asks']], 'T': data.get('ts')}

    def orderBook(self, symbol: str, limit: int = 5):
        _, symbolInfo = self.coinInfo(symbol)
        return self._ccxt.fetch_order_book(symbol=symbolInfo.get('symbol'), limit=limit)

    def trades(self, symbol: str, limit: int) -> list:
        """成交历史,qty 为币数;side 是吃单方向,吃单卖出=买方挂单"""
        instId = self._instId(symbol)
        rt = tryCatch(lambda: self._ccxt.publicGetMarketTrades(params={'instId': instId, 'limit': limit}))
        if not rt or not rt.get('data'):
            return []
        ct = self._ctVal(instId)
        return [{'price': t['px'],
                 'qty': _num(t['sz']) * ct,
                 'quoteQty': _num(t['px']) * _num(t['sz']) * ct,
                 'isBuyerMaker': t['side'] == 'sell',
                 'time': t.get('ts')}
                for t in rt['data']]

    def tickers(self, symbol: str):
        """最新币价"""
        rt = tryCatch(lambda: self._ccxt.publicGetMarketTicker(params={'instId': self._instId(symbol)}))
        if not rt or not rt.get('data'):
            return None
        data = rt['data'][0]
        data['price'] = data.get('last')
        return data

    def fundingRate(self, symbol: str, category: str = kSwap):
        """资金费率"""
        rt = tryCatch(lambda: self._ccxt.publicGetPublicFundingRate(params={'instId': self._instId(symbol)}))
        if not rt or not rt.get('data'):
            return None
        return rt['data']

    # ── ws监听 ──
    def _wsListen(self) -> list[tuple]:
        return [(self._wsSpot, 'SPOT'),
                (self._wsSwap, 'SWAP')]
