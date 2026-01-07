from server.market.baseExchange import *
kMaxLimit = 100  # 最大k线数据

# todo:批次下单没做


class okex(baseExchange):
    _name = "okex"

    def __init__(self, description):
        super().__init__(description, kMaxLimit)

    def create(self, config):
        self._ccxt = ccxt.okx()
        self._ccxt.apiKey = config['apiKey']
        self._ccxt.secret = config['secret']
        self._ccxt.password = config['passphrase']
        self._ccxt.timeout = 3000
        self._ccxt.enableRateLimit = True

    # def showApi(self):
    #     print("~~~~私有~~~~~",*list(dir(ccxt.okx())), sep='\n')
    #     print('~~~~支持信息~~~~~~')
    #     logFormat(self._ccxt.has)

    # SPOT：币币,MARGIN：币币杠杆,SWAP：永续合约,FUTURES：交割合约,OPTION：期权
    def futureOrder(self, **kwargs):
        state = kwargs['state']
        symbol = strReplace(kwargs['symbol'])
        params = {'instId': symbol}
        if state == 'buy' or state == 'sell':
            params.update({
                'tdMode': 'isolated',  # 交易模式(isolated逐，cross全)
                'side': state,  # 订单方向，buy sell
                'posSide': state == 'buy' and 'long' or 'short',  # 持仓方向，long short 平仓
                'ordType': 'market',  # 类型，market，limit，
                'sz': kwargs['amount'],  # 委托数量
            })
            if kwargs.get('price'):  # 限价委托
                params['ordType'] = 'limit'
                params['px'] = kwargs.get('price')
            if kwargs.get('tp'):  # 止盈
                params['tpTriggerPx'] = kwargs.get('tp')
                params['tpOrdPx'] = '-1'
            if kwargs.get('sl'):  # 止损
                params['slTriggerPx'] = kwargs.get('sl')
                params['slOrdPx'] = '-1'
            # 设置杠杆倍数，如有挂单会失败
            rt = self._ccxt.privatePostAccountSetLeverage(params={
                'instId': symbol,
                'posSide': state == 'buy' and 'long' or 'short',
                'lever': kwargs.get("lv") and str(kwargs['lv']) or '1',
                'mgnMode': 'isolated'})
            # print('杠杆倍数:', rt['data'][0].get('lever'))
        elif state == 'cancel':
            params['ordId'] = kwargs['id']
        elif state == 'bill':
            params['mgnMode'] = 'isolated'
            params['posSide'] = kwargs['posSide']
        # print("~~~params~~~",state, params)
        rt = switchFn({'buy': self._ccxt.privatePostTradeOrder,
                       'sell': self._ccxt.privatePostTradeOrder,
                       'cancel': self._ccxt.privatePostTradeCancelOrder,
                       'bill': self._ccxt.privatePostTradeClosePosition},
                      key=state, params=params)
        return rt

    # spot现货，swap永续，future期权              symbol:BTC-USD-SWAP #BTC/USDT
    def getKline(self, symbol, seTime, timeframe='5m', limit=0):
        category, newSymbol = slit(symbol, '_')
        params = {'instId': strReplace(newSymbol),
                  # okx获取k线特别奇葩需要延后一天，可用其他币安k线替代
                  'after': str2ms(seTime[0], 24),
                  'bar': timeframe,  # [1m/3m/5m/15m/30m/1H/2H/4H]
                  'limit': limit == 0 and self._maxLimit or limit}
        if category == 'spot':
            kLineData = self._ccxt.publicGetMarketHistoryIndexCandles(
                params=params)
        elif category == "swap":
            kLineData = self._ccxt.publicGetMarketHistoryCandles(params=params)
        self._pd.format(kLineData['data'], style='candle', utc=self._utc)
        return self._pd.get()
