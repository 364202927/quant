from include import *
import ccxt
# import abc


# print(ccxt.__version__)
# dir (ccxt.hitbtc ()) #ccxt获取所有函数

class baseExchange():
    __description = None #描述
    _maxlimit = 1 #每个交易所不一样，最大页数据
    _ccxt = None
    _pd = None

    def __init__(self, description, maxLimit):
        self.__description = description
        self._maxLimit = maxLimit
        self._pd = pdData()

    def name(self):
        return type(self).__name__
    def des(self):
        return self.__description
    def showApi(self,strIndex = 'private'):
        print("~~~~调用方式~~~~~~","public/private + get/post + path, 驼峰编码")
        logFormat(self._ccxt.api[strIndex])

    #注册
    def enroll(self, apiKey, secret):
        exchangeClass = getattr(ccxt, self.name())
        self._ccxt = exchangeClass({
            'apiKey': apiKey,
            'secret': secret,
            'timeout': 30000,
            'enableRateLimit': True,
        })
    
    # 获取市场全种类信息
    def markets(self):
        market = self._ccxt.load_markets()
        dicMarket = {}
        for symbol, market in market.items():
            dicMarket[symbol] = {'type':market['type']}
        return dicMarket

    #账号数据
    def account(self):
        return self._ccxt.fetch_balance()
    
    #获取一段时间的k线，limit默认应该是交易所最大值
    def getKline(self, symbol, seTime,  timeframe='5m',limit = 0):
        print("~~~~~~",self._ex.fetch_ohlcv(symbol = symbol, timeframe = timeframe,since = self._ex.parse8601(seTime[1]), limit=self._maxLimit))
        pass
    #获取币种历史 (spot现货，swap永续，future期权) , [开始,结束时间], 时间粒度, 保存到文件
    def getHistoryCandles(self, symbol, seTime, timeframe = '5m',fileName = ""):
        #todo:获取时间时，会出现正序和倒序,这个函数还没完成
        pf = self.getKline(symbol, seTime)
        allData = [pf]

        # print("~~~~frist~~~~~")
        # self._pd.show()
        # exit()
        while True:
            # isSequence = self._pd.get(0,0) >= self._pd.get(-1,0)
            # startTime = isSequence == True and self._pd.get(0,0) or self._pd.get(-1,0)
            startTime = seTime[0]
            stopTime = self._pd.get(-1,0)
            # print("最后一次获取的时间搓",self._pd.get(0,0),  self._pd.get(-1,0))
            
            pf = self.getKline(symbol, [str(startTime), str(stopTime)])
            print("获取k线时间",startTime," <",stopTime,":::",str2time(startTime) < stopTime,"~~~",pf.shape[0])
            allData.append(pf)
            # self._pd.show()
            # time.sleep(1)
            # print("~~~~~~~~",pf.shape[0])
            # if str2time(startTime) >= stopTime:
            if pf.shape[0] < self._maxlimit:
                break
        # print("finsh",allData,isinstance(allData[0], pdData))
        self._pd.format(allData)
        self._pd.show()
        # 保存到文件
        if fileName != "":
            self._pd.save2File(self.name()+"_"+fileName)
        # 时间粒度
        if timeframe != '5m':
            self._pd.resample(timeframe)
        return self._pd.get()
    #获取多币种k线
    def oblcv(self,symbol, timeframe = "5m"):
        data = self._ccxt.fetch_ohlcv(symbol= symbol, timeframe = timeframe)
        print("~~~data~~~~")

    def orders(self):
        pass
        # 获取盘口深度数据
        # try:
        #     response = await exchange.fetch_order_book(symbol="BTC/USDT", limit=5)
        #     print(response)
        # except ccxt.NetworkError as e:
        #     print(exchange.id, 'fetch_order_book failed due to a network error:', str(e))
        # except ccxt.ExchangeError as e:
        #     print(exchange.id, 'fetch_order_book failed due to exchange error:', str(e))
        # except Exception as e:
        #     print(exchange.id, 'fetch_order_book failed with:', str(e))
        # 限价委托
        # result = exchange.create_limit_buy_order(symbol="BTC/USDT", amount=1, price=1)
        # print("限价买入委托单结果：", result)
