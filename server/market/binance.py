from server.market.baseExchange import *
# from concurrent.futures import ThreadPoolExecutor

kMaxLimit = 1000  # 现货最大k线
kfMaxLimit = 1500  # 合约最大

# batchOrders 批量下单，最多5个
# https://www.binance.com/zh-CN/trade-rule 币种交易规则
# https://binance-docs.github.io/apidocs/pm/cn  api


class binance(baseExchange):
    _name = "币安"

    def __init__(self, description):
        super().__init__(description, kfMaxLimit)

    def _accFutures(self, account):
        return account['futures']['free']

    def _futureFind(self, **kwargs):
        # papiGetUmOpenOrder #查挂单
        # papiGetUmOrder
        params = {'symbol': kwargs.get('symbol'),
                  # 获取历史条数
                  'limit': kwargs.get('limit') and kwargs.get('limit') or 1,
                  'timestamp': binanceTimestamp()}
        if kwargs.get('orderId'):
            params['orderId'] = kwargs.get('orderId')
        rt = self._ccxt.papiGetUmAllOrders(params=params)
        # um账号成交记录
        # todo改成:papiGetUmUserTrades
        # 批量返回
        if kwargs.get('limit') and int(kwargs['limit']) > 0:
            return rt
        rt = rt[0]
        statusTransform = {
            'NEW': 'open',
            'FILLED': 'closed',
            'CANCELED': 'cancel'}  # 状态转换到和现货一样
        # print("~~~~findFuture~~~~", rt)
        return {'status': statusTransform[rt.get('status')],
                'time': rt.get('time'),
                'updateTime': rt.get('updateTime'),
                'orderId': rt.get('orderId'),
                'positionSide': rt.get('positionSide'),
                'origQty': rt.get('status') == 'NEW' and -1 or rt.get('origQty'),
                'avgPrice': rt.get('avgPrice'),
                'cumQuote': rt.get('cumQuote')}

    # 只有统一账号才可下单 um(u本位)和cm(币本位,不支持)
    def _futureOrder(self, **kwargs):
        state = kwargs['state']
        symbol = kwargs['symbol']['id']
        params = {'symbol': symbol,
                  'timestamp': binanceTimestamp()}
        if state == 'buy' or state == 'sell':
            params.update({
                'side': state.upper(),  # 订单方向，buy sell
                'positionSide': kwargs['posSide'],  # 持仓方向
                'quantity': int(kwargs['amount']),  # 委托数量
                'type': 'LIMIT',
                'timeInForce': 'GTC'})
            if kwargs.get('price'):
                params['price'] = kwargs.get('price')
            # if not kwargs.get('price'): #市价
            else:  # 市价
                params['type'] = 'MARKET'
                del params['timeInForce']
            # todo：添加止损单
            # 设置倍数
            if kwargs.get("lv"):
                rt = self._ccxt.papiPostUmLeverage(
                    params={
                        'symbol': symbol,
                        'leverage': kwargs.get("lv"),
                        'timestamp': binanceTimestamp()})
        elif state == 'cancel':
            params['orderId'] = kwargs['id']
        rt = switchFn({'buy': self._ccxt.papiPostUmOrder,  # U本位fapiPrivatePostOrder
                       'sell': self._ccxt.papiPostUmOrder,
                       # (symbol,orderId,timestamp)
                       'cancel': self._ccxt.papiDeleteUmOrder,
                       'bill': self._ccxt.papiPostUmOrder},
                      key=state,
                      params=params)
        return self._futureFind(symbol=symbol, orderId=rt['orderId'])

    def _futureCancal(self, **kwargs):
        return self._ccxt.papiDeleteUmOrder(
            params={
                'symbol': kwargs['symbol'],
                'orderId': kwargs['orderId'],
                'timestamp': binanceTimestamp()})

    # 查询持仓
    def checkPosition(self):
        def risk():
            return self._ccxt.papiGetUmPositionRisk(
                params={'timestamp': binanceTimestamp()})
        rt, info = tryExecution(risk)
        if rt:
            return info
        return []
    # 查询账户

    def account(self):
        dict = {'total': {},
                'used': {},
                'free': {}}
        super().account()  # 现货账号
        for key, sub_dict in self._info['acc'].items():
            for sub_key, sub_value in sub_dict.items():
                if sub_value > 0:
                    name = sub_key
                    dict[key][name] = sub_value
        self._info['acc'] = dict
        # 统一账户
        portfolioAcc = self._ccxt.sapiGetPortfolioAccount()
        self._info['acc']['futures'] = {"uniMMR": portfolioAcc['uniMMR'],  # 统一账号的风险
                                        "total": portfolioAcc['accountEquity'],
                                        "free": portfolioAcc['totalAvailableBalance'],
                                        "used": portfolioAcc['accountInitialMargin']}
        # 合约账户
        # acc = self._ccxt.fapiPrivateV2GetAccount()['assets']
        # for data in acc:
        #     if float(data['walletBalance']) > 0:
        #         self._info['acc']['total'].update({data['asset']:data['walletBalance']})
        #         self._info['acc']['free'].update({data['asset']:data['maxWithdrawAmount']})
        #         self._info['acc']['used'].update({data['asset']:data['initialMargin']})
        return self._info['acc']

    # spot现货，swap永续，future期权
    def getKline(self, symbol, seTime, timeframe='5m', limit=0):
        category, newSymbol = slit(symbol, '_')
        if category == 'spot':
            self._maxLimit = kMaxLimit
            kLineData = super().getKline(
                newSymbol, seTime, limit=limit == 0 and self._maxLimit or limit)
        elif category == "swap":  # dapi(币本位)、fapi(u本位)、eapi(欧式期权)
            self._maxLimit = kfMaxLimit
            # print("~~~~~a~~~~~",seTime[0])
            # print("~~~~~b~~~~~",seTime[1])
            params = {
                'symbol': newSymbol,
                'interval': timeframe,
                'startTime': str2ms(seTime[0]),
                'endTime': str2ms(seTime[1]),
                'limit': limit == 0 and kfMaxLimit or limit}
            if newSymbol[-5:] == '_PERP':  # 币本位
                kLineData = self._ccxt.dapiPublicGetKlines(params=params)
            else:
                kLineData = self._ccxt.fapiPublicGetKlines(params=params)
        pd = pdData()
        pd.format(kLineData, style='candle', utc=self._utc)
        return pd.get()

    # 获取现货或u本位深度
    def depth(self, symbol, limit):  # limit(5,10,20,50,100,500,1000)
        category, newSymbol = slit(symbol, '_')
        params = {'symbol': newSymbol, 'limit': limit}
        if category == "spot":
            return self._ccxt.publicGetDepth(params=params)
        return self._ccxt.fapiPublicGetDepth(params=params)
    # 获取成交历史

    def trades(self, symbol, limit):  # limit max = 1000
        category, newSymbol = slit(symbol, '_')
        params = {'symbol': newSymbol, 'limit': limit}
        if category == "spot":
            return self._ccxt.publicGetTrades(params=params)
        return self._ccxt.fapiPublicGetTrades(params=params)
    # 最新币价

    def tickers(self, symbol):
        category, newSymbol = slit(symbol, '_')
        params = {'symbol': newSymbol}
        if category == "spot":
            return self._ccxt.publicGetTickerPrice(
                params={'symbol': newSymbol})
        return self._ccxt.fapiPublicGetTickerPrice(params=params)
        # /fapi/v1/ticker/price

    # 获取最优价
    def bookTickers(self, symbol):
        category, newSymbol = slit(symbol, '_')
        params = {'symbol': newSymbol}
        return self._ccxt.fapiPublicGetTickerBookTicker(
            params=params)  # todo:只做了u本位
