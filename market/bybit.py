from market.baseExchange import *
kUtcTime = 7 #交易所获取k线utc时间
kMaxLimit = 1000 #bybit获取最大k线数据

# bybit只能查询到统一交易账户的钱，其余存放在理财和余币宝的全部查不到
class bybit(baseExchange):
    _name = "bybit"

    def __init__(self, description):
        super().__init__(description, kMaxLimit)

    # def account(self):
        # user = self._ex.privateGetV5AccountWalletBalance(params={'accountType':'FUND'})
    #     user = self._ex.privateGetV5AssetTransferQueryAccountCoinsBalance(params={'accountType':'UNIFIED'})
    #     # logFormat(user)
        # print(user)
        # return user

    #获取一段时间的k线
    def getKline(self, symbol, seTime, timeframe='5m',limit = 0):
        category = symbol[:4]
        newSymbol = symbol[5:]
        params={'category':category,
                'symbol':newSymbol,
                'interval':str(sec2min(timeFrame2int(timeframe))), #获取12h后的时间会报错，续改成dwm
                'start':str2ms(seTime[0]),
                'end':str2ms(seTime[1]),
                'limit':limit == 0 and kMaxLimit or limit}
        kLineData = self._ccxt.publicGetV5MarketKline(params)["result"]["list"]
        self._pd.format(kLineData, kUtcTime)
        return self._pd.get()