from server.market.baseExchange import *
from server.utils.science import binanceTimestamp
from server.utils import timeFrame2Float, sec2min,logFormat
import json

kMaxLimit = 1000   # 现货最大 K 线
kfMaxLimit = 1500  # 合约最大
kPm = 'PortfolioMargin'
# kMarket, kLimit = 'MARKET', 'LIMIT'
# kUm, kCm, kEo = 'um', 'cm', 'eo'  # U本位、币本位、期权

STATUS_MAP = {'NEW': 'open', 'FILLED': 'closed', 'CANCELED': 'cancel'}

class binance(baseExchange):

    def __init__(self, description: str):
        super().__init__(description, kfMaxLimit)

    def account(self) -> dict:
        accDict = {'total': {}, 'used': {}, 'free': {}}
        # tryCatch(lambda: super(binance, self).account())
        # print('bianacc')
        super().account()
        for key, sub_dict in self._info.get('acc', {}).items():
            for sub_key, sub_value in sub_dict.items():
                if sub_value > 0:
                    accDict[key][sub_key] = sub_value
        #资金大于10w刀使用的是pm3查询不是sapiGetPortfolioAccount
        self._info['acc'] = accDict
        portfolioAcc = self._ccxt.sapiGetPortfolioAccount()
        self._info['acc'][kPm] = {
                'uniMMR': portfolioAcc['uniMMR'],
                'total': portfolioAcc['accountEquity'],
                'free': portfolioAcc['totalAvailableBalance'],
                'used': portfolioAcc['accountInitialMargin']}
        return self._info['acc']
    
    def _accFutures(self, account: dict) -> float:
        return account[kPm]['free']
    
    def _portfolioMargin(self,account: dict) -> float:
        return account[kPm]['free']


    def _futureFind(self, **kwargs):
        """查询合约订单"""
        category = kwargs.get('category', kUm)
        symbol = kwargs.get('symbol')
        params = {
            'symbol': symbol,
            'limit': kwargs.get('limit', 1),
            'timestamp': binanceTimestamp()
        }
        if kwargs.get('orderId'):
            params['orderId'] = kwargs['orderId']

        rt = tryCatch(lambda: switchFn({
            kUm: self._ccxt.papiGetUmAllOrders,
            kCm: self._ccxt.papiGetCmAllOrders
        }, key=category, params=params))

        if not rt:
            return None

        if kwargs.get('limit') and int(kwargs['limit']) > 1:
            return rt

        order = rt[0] if rt else {}
        return {
            'status': STATUS_MAP.get(order.get('status'), order.get('status')),
            'time': order.get('time'),
            'updateTime': order.get('updateTime'),
            'orderId': order.get('orderId'),
            'positionSide': order.get('positionSide'),
            'origQty': -1 if order.get('status') == 'NEW' else order.get('origQty'),
            'avgPrice': order.get('avgPrice'),
            'cumQuote': order.get('cumQuote')
        }

    def _futureOrder(self, **kwargs):
        """合约下单 (U本位/币本位)"""
        state = kwargs['state']
        symbol = kwargs['symbol']['id']
        category = kwargs.get('category', kUm)

        params = {'symbol': symbol, 'timestamp': binanceTimestamp()}

        if state in (kBuy, kSell):
            isLimit = kwargs.get('price') is not None
            params.update({
                'side': state.upper(),
                'positionSide': kwargs['posSide'],
                'quantity': kwargs['amount'],
                'type': kLimit if isLimit else kMarket
            })

            if isLimit:
                params['price'] = kwargs['price']
                params['timeInForce'] = kwargs.get('timeInForce', 'GTC')

            if kwargs.get('lv'):
                lvParams = {'symbol': symbol, 'leverage': kwargs['lv'], 'timestamp': binanceTimestamp()}
                tryCatch(lambda: switchFn({
                    kUm: self._ccxt.papiPostUmLeverage,
                    kCm: self._ccxt.papiPostCmLeverage
                }, key=category, params=lvParams))

        elif state == 'cancel':
            params['orderId'] = kwargs['orderId']

        orderApi = self._ccxt.papiPostUmOrder if category == kUm else self._ccxt.papiPostCmOrder
        cancelApi = self._ccxt.papiDeleteUmOrder if category == kUm else self._ccxt.papiDeleteCmOrder

        rt = tryCatch(lambda: switchFn({
            kBuy: orderApi, kSell: orderApi, 'cancel': cancelApi
        }, key=state, params=params))

        if not rt:
            return None
        return self._futureFind(category=category, symbol=symbol, orderId=rt.get('orderId'))

    def _futureCancal(self, **kwargs):
        """取消合约订单"""
        category = kwargs.get('category', kUm)
        params = {
            'symbol': kwargs['symbol'],
            'orderId': kwargs['orderId'],
            'timestamp': binanceTimestamp()
        }
        return tryCatch(lambda: switchFn({
            kUm: self._ccxt.papiDeleteUmOrder,
            kCm: self._ccxt.papiDeleteCmOrder
        }, key=category, params=params))

    def _batchOrders(self, category: str, orders: list[dict]):
        """批量下单，最多5单"""
        batchList = []
        for order in orders:
            isLimit = order.get('price') is not None
            item = {
                'symbol': order['symbol'],
                'side': order['side'].upper(),
                'positionSide': order['posSide'],
                'quantity': str(order['amount']),
                'type': kLimit if isLimit else kMarket
            }
            if isLimit:
                item['price'] = str(order['price'])
                item['timeInForce'] = order.get('timeInForce', 'GTC')
            batchList.append(item)

        params = {'batchOrders': json.dumps(batchList), 'timestamp': binanceTimestamp()}
        return tryCatch(lambda: switchFn({
                                kUm: self._ccxt.papiPostUmBatchOrders,
                                kCm: self._ccxt.papiPostCmBatchOrders}, 
                            key=category, params=params))

    def optionOrder(self, state: str, **kwargs):
        """期权下单 state: 'buy'/'sell'/'cancel'"""
        symbol = kwargs['symbol']
        params = {'symbol': symbol, 'timestamp': binanceTimestamp()}

        if state in (kBuy, kSell):
            isLimit = kwargs.get('price') is not None
            params.update({
                'side': state.upper(),
                'quantity': kwargs['amount'],
                'type': kLimit if isLimit else kMarket})
            if isLimit:
                params['price'] = kwargs['price']
                params['timeInForce'] = kwargs.get('timeInForce', 'GTC')
            if kwargs.get('clientOrderId'):
                params['clientOrderId'] = kwargs['clientOrderId']
        elif state == 'cancel':
            params['orderId'] = kwargs['orderId']

        return tryCatch(lambda: switchFn({
            kBuy: self._ccxt.papiPostEoOrder,
            kSell: self._ccxt.papiPostEoOrder,
            'cancel': self._ccxt.papiDeleteEoOrder
        }, key=state, params=params))

    def optionFind(self, symbol: str, orderId: str | None = None, limit: int = 1):
        """查询期权订单"""
        params = {'symbol': symbol, 'limit': limit, 'timestamp': binanceTimestamp()}
        if orderId:
            params['orderId'] = orderId
        return tryCatch(lambda: self._ccxt.papiGetEoHistoryOrders(params=params))

    def checkPosition(self, category: str = kUm, symbol: str | None = None):
        """查询持仓"""
        params = {'timestamp': binanceTimestamp()}
        if symbol:
            params['symbol'] = symbol
        return tryCatch(lambda: switchFn({
            kUm: self._ccxt.papiGetUmPositionRisk,
            kCm: self._ccxt.papiGetCmPositionRisk
        }, key=category, params=params))

    def _marketKline(self, symbol: str, seTime: list, timeframe: str = '5m', limit: int = 0):
        category, newSymbol = slit(symbol, '_')
        if category == kSpot:
            self._maxLimit = kMaxLimit
            kLineData = super()._marketKline(newSymbol, seTime, limit=limit if limit else self._maxLimit)
        elif category == kSwap:
            self._maxLimit = kfMaxLimit
            params = {'symbol': newSymbol,
                'interval': timeframe,
                'limit': limit if limit else kfMaxLimit}
            if len(seTime) > 0:
                params['startTime'] = str2ms(seTime[0])
                params['endTime'] = str2ms(seTime[1])
            api = self._ccxt.dapiPublicGetKlines if newSymbol.endswith('_PERP') else self._ccxt.fapiPublicGetKlines #期权和合约
            kLineData = tryCatch(lambda: api(params=params))
            if not kLineData:
                return None
        else:
            err('币安还没完成以下币种获取:',symbol)
            return None
        #格式化k线
        pd = pdData()
        pd.format(kLineData, utc = self._utc) #对齐当前国家时区
        return pd.get()

    def depth(self, symbol: str, limit: int):
        """深度数据"""
        category, newSymbol = slit(symbol, '_')
        params = {'symbol': newSymbol, 'limit': limit}
        return tryCatch(lambda: switchFn({
            'spot': self._ccxt.publicGetDepth,
            'swap': self._ccxt.fapiPublicGetDepth
        }, key=category, params=params))

    def trades(self, symbol: str, limit: int):
        """成交历史"""
        category, newSymbol = slit(symbol, '_')
        params = {'symbol': newSymbol, 'limit': limit}
        return tryCatch(lambda: switchFn({
            'spot': self._ccxt.publicGetTrades,
            'swap': self._ccxt.fapiPublicGetTrades
        }, key=category, params=params))

    def tickers(self, symbol: str):
        """最新币价"""
        category, newSymbol = slit(symbol, '_')
        params = {'symbol': newSymbol}
        return tryCatch(lambda: switchFn({
            'spot': self._ccxt.publicGetTickerPrice,
            'swap': self._ccxt.fapiPublicGetTickerPrice
        }, key=category, params=params))

    def bookTickers(self, symbol: str):
        """最优价"""
        category, newSymbol = slit(symbol, '_')
        params = {'symbol': newSymbol}
        return tryCatch(lambda: switchFn({
            'spot': self._ccxt.publicGetTickerBookTicker,
            'swap': self._ccxt.fapiPublicGetTickerBookTicker
        }, key=category, params=params))

    def fundingRate(self, symbol: str, category: str = kUm):
        """资金费率"""
        _, newSymbol = slit(symbol, '_')
        params = {'symbol': newSymbol}
        return tryCatch(lambda: switchFn({
            kUm: self._ccxt.fapiPublicGetFundingRate,
            kCm: self._ccxt.dapiPublicGetFundingRate
        }, key=category, params=params))

    def setPositionMode(self, dualSide: bool = True, category: str = kUm):
        """设置持仓模式 dualSide: True=双向持仓, False=单向持仓"""
        params = {'dualSidePosition': str(dualSide).lower(), 'timestamp': binanceTimestamp()}
        return tryCatch(lambda: switchFn({
            kUm: self._ccxt.papiPostUmPositionSideDual,
            kCm: self._ccxt.papiPostCmPositionSideDual
        }, key=category, params=params))

    def setMarginType(self, symbol: str, marginType: str = 'CROSSED', category: str = kUm):
        """设置保证金类型 marginType: 'CROSSED'(全仓) 或 'ISOLATED'(逐仓)"""
        params = {'symbol': symbol, 'marginType': marginType, 'timestamp': binanceTimestamp()}
        return tryCatch(lambda: switchFn({
            kUm: self._ccxt.papiPostUmMarginType,
            kCm: self._ccxt.papiPostCmMarginType
        }, key=category, params=params))
