from server.market.baseExchange import *
from server.utils import timeFrame2Float, sec2min
kMaxLimit = 1000
kMarket, kLimit = 'Market', 'Limit'
kLinear, kInverse, kOption = 'linear', 'inverse', 'option'
CATEGORY_MAP = {'spot': 'spot', 'swap': kLinear}
STATUS_MAP = {
    'New': 'open', 'PartiallyFilled': 'open', 'Filled': 'closed',
    'Cancelled': 'cancel', 'Rejected': 'rejected'
}

class bybit(baseExchange):
    """Bybit 交易所实现"""
    _name = "bybit"

    def __init__(self, description: str):
        super().__init__(description, kMaxLimit)

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

    def account(self) -> dict:
        """查询账户"""
        accDict = {'total': {}, 'used': {}, 'free': {}}

        rt = tryCatch(lambda: self._ccxt.privateGetV5AccountWalletBalance(params={'accountType': 'UNIFIED'}))
        if rt and rt.get('result', {}).get('list'):
            wallet = rt['result']['list'][0]
            accDict['total']['equity'] = wallet.get('totalEquity')
            accDict['free']['available'] = wallet.get('totalAvailableBalance')
            accDict['used']['margin'] = wallet.get('totalInitialMargin')

            for coin in wallet.get('coin', []):
                balance = float(coin.get('walletBalance', 0))
                if balance > 0:
                    name = coin['coin']
                    accDict['total'][name] = float(coin['walletBalance'])
                    accDict['free'][name] = float(coin['availableToWithdraw'])
                    accDict['used'][name] = float(coin['locked'])

        self._info['acc'] = accDict
        return self._info['acc']

    def _accPm(self, account: dict) -> float:
        return account.get('free', {}).get('available', 0)

    def _findOrder(self, symbol: str, orderId: str | None = None, category: str = kLinear, limit: int = 1):
        """查询合约订单"""
        params = {
            'category': category,
            'symbol': symbol,
            'limit': limit
        }
        if orderId:
            params['orderId'] = orderId

        rt = tryCatch(lambda: self._ccxt.privateGetV5OrderHistory(params=params))
        if not rt or not rt.get('result', {}).get('list'):
            return None

        orders = rt['result']['list']
        if limit > 1:
            return orders

        order = orders[0] if orders else {}
        return {
            'status': STATUS_MAP.get(order.get('orderStatus'), order.get('orderStatus')),
            'time': order.get('createdTime'),
            'updateTime': order.get('updatedTime'),
            'orderId': order.get('orderId'),
            'positionSide': order.get('positionIdx'),
            'origQty': order.get('qty'),
            'avgPrice': order.get('avgPrice'),
            'cumQuote': order.get('cumExecValue')
        }

    def _contractOrder(self, state: str, symbol: dict | str, amount: float, price: float | None = None,
                     posSide: str | None = None, category: str = kLinear, timeInForce: str | None = None,
                     posIdx: int = 0, lv: int | None = None, orderId: str | None = None):
        """合约下单 (U本位/币本位)"""
        symbol_id = symbol['id'] if isinstance(symbol, dict) else symbol

        params = {'category': category, 'symbol': symbol_id}

        if state in (kBuy, kSell):
            isLimit = price is not None
            params.update({
                'side': state.capitalize(),
                'orderType': kLimit if isLimit else kMarket,
                'qty': str(amount),
                'positionIdx': posIdx
            })

            if isLimit:
                params['price'] = str(price)
                params['timeInForce'] = timeInForce or 'GTC'
            else:
                params['timeInForce'] = 'IOC'

            if lv:
                self._setLeverage(category, symbol_id, lv)

        elif state == 'cancel':
            params['orderId'] = orderId

        rt = tryCatch(lambda: switchFn({
            kBuy: self._ccxt.privatePostV5OrderCreate,
            kSell: self._ccxt.privatePostV5OrderCreate,
            'cancel': self._ccxt.privatePostV5OrderCancel
        }, key=state, params=params))

        if not rt or rt.get('retCode') != 0:
            err("bybit order error:", rt)
            return None

        rt_orderId = rt.get('result', {}).get('orderId')
        return self._findOrder(symbol=symbol_id, orderId=rt_orderId, category=category)

    def _cancelOrder(self, symbol: str, orderId: str, category: str = kLinear):
        """取消订单"""
        params = {
            'category': category,
            'symbol': symbol,
            'orderId': orderId
        }
        return tryCatch(lambda: self._ccxt.privatePostV5OrderCancel(params=params))

    def _batchOrders(self, category: str, orders: list[dict]):
        """批量下单，最多10单"""
        if len(orders) > 10:
            err("bybit batchOrders: 最多10单")
            return None

        requestList = []
        for order in orders:
            isLimit = order.get('price') is not None
            item = {
                'symbol': order['symbol'],
                'side': order['side'].capitalize(),
                'orderType': kLimit if isLimit else kMarket,
                'qty': str(order['amount']),
                'positionIdx': order.get('posIdx', 0)
            }
            if isLimit:
                item['price'] = str(order['price'])
                item['timeInForce'] = order.get('timeInForce', 'GTC')
            else:
                item['timeInForce'] = 'IOC'
            requestList.append(item)

        params = {'category': category, 'request': requestList}
        rt = tryCatch(lambda: self._ccxt.privatePostV5OrderCreateBatch(params=params))
        if not rt or rt.get('retCode') != 0:
            err("bybit batchOrders error:", rt)
            return None
        return rt.get('result', {}).get('list', [])

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

    def checkPosition(self, category: str = kLinear, symbol: str | None = None) -> list:
        """查询持仓"""
        params = {'category': category}
        if symbol:
            params['symbol'] = symbol

        rt = tryCatch(lambda: self._ccxt.privateGetV5PositionList(params=params))
        if not rt or not rt.get('result', {}).get('list'):
            return []
        return rt['result']['list']

    def _setLeverage(self, category: str, symbol: str, leverage: int):
        """内部设置杠杆"""
        params = {
            'category': category,
            'symbol': symbol,
            'buyLeverage': str(leverage),
            'sellLeverage': str(leverage)
        }
        return tryCatch(lambda: self._ccxt.privatePostV5PositionSetLeverage(params=params))

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

    def _marketKline(self, symbol: str, beginTime: int | None, endTime: int | None, timeframe: str = '5m', limit: int = 0):
        """获取 K 线数据"""
        category, newSymbol = self._getCategory(symbol)
        effectiveLimit = limit if limit > 0 else self._maxLimit
        params = {
            'category': category,
            'symbol': newSymbol,
            'interval': str(sec2min(int(timeFrame2Float(timeframe)))),
            'limit': effectiveLimit
        }
        if beginTime is not None:
            params['start'] = beginTime
        if endTime is not None:
            params['end'] = endTime

        rt = tryCatch(lambda: self._ccxt.publicGetV5MarketKline(params))
        if not rt or not rt.get('result', {}).get('list'):
            return None

        pd = pdData()
        pd.format(rt['result']['list'], style='candle', utc=self._utc)
        return pd.get()

    def depth(self, symbol: str, limit: int):
        """深度数据"""
        params = self._rtParams(symbol, limit)
        rt = tryCatch(lambda: self._ccxt.publicGetV5MarketOrderbook(params))
        if not rt or not rt.get('result'):
            return None

        data = rt['result']
        return {'bids': data['b'], 'asks': data['a'], 'T': data.get('ts')}

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

    def openOrders(self, category: str = kLinear, symbol: str | None = None) -> list:
        """查询当前挂单"""
        params = {'category': category}
        if symbol:
            params['symbol'] = symbol

        rt = tryCatch(lambda: self._ccxt.privateGetV5OrderRealtime(params=params))
        if not rt or not rt.get('result', {}).get('list'):
            return []
        return rt['result']['list']

    def cancelAllOrders(self, category: str = kLinear, symbol: str | None = None):
        """批量取消订单"""
        params = {'category': category}
        if symbol:
            params['symbol'] = symbol
        return tryCatch(lambda: self._ccxt.privatePostV5OrderCancelAll(params=params))
