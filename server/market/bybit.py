from server.market.baseExchange import *
# kUtcTime = 7        #交易所获取k线utc时间
kMaxLimit = 1000  # bybit获取最大k线数据

# bybit只能查询到统一交易账户的钱，其余存放在理财和余币宝的全部查不到


class bybit(baseExchange):
    _name = "bybit"

    def __init__(self, description):
        super().__init__(description, kMaxLimit)
        # print("~~~~",self._maxLimit)

    # def account(self):
    #     dict = {'total': {},
    #             'used': {},
    #             'free': {}}
        # user = self._ex.privateGetV5AccountWalletBalance(params={'accountType':'FUND'})
    #     user = self._ex.privateGetV5AssetTransferQueryAccountCoinsBalance(params={'accountType':'UNIFIED'})
    #     # logFormat(user)
        # print(user)
        # return user

    # 返回{category，symbol，limit}
    def _rtParams(self, symbol, limit=0):
        category = {'spot': 'spot', "swap": 'linear'}
        type, newSymbol = slit(symbol, '_')
        params = {'category': category[type],
                  'symbol': newSymbol,
                  'limit': limit}
        if limit == 0:
            del params['limit']
        return params

    # 获取一段时间的k线
    def getKline(self, symbol, seTime, timeframe='5m', limit=0):
        category, newSymbol = slit(symbol, '_')
        params = {'category': category,
                  'symbol': newSymbol,
                  # 获取12h后的时间会报错，续改成dwm
                  'interval': str(sec2min(timeFrame2int(timeframe))),
                  'start': str2ms(seTime[0]),
                  'end': str2ms(seTime[1]),
                  'limit': limit == 0 and self._maxLimit or limit}
        kLineData = self._ccxt.publicGetV5MarketKline(params)["result"]["list"]
        self._pd.format(kLineData, style='candle', utc=self._utc)
        return self._pd.get()

    # 获取深度
    def depth(self, symbol, limit):
        # type, newSymbol = slit(symbol,'_')
        # category = {'spot':'spot',"swap":'linear'}
        # params = {'category':category[type],
        #           'symbol': newSymbol,
        # 		    'limit':limit}
        data = self._ccxt.publicGetV5MarketOrderbook(
            self._rtParams(symbol, limit))["result"]
        return {
            'bids': data['b'],
            'asks': data['a'],
            'T': data['cts']}  # 对齐币安格式

    # 成交历史
    def trades(self, symbol, limit):  # limit max = 1000
        tData = []
        data = self._ccxt.publicGetV5MarketRecentTrade(
            self._rtParams(symbol, limit))["result"]['list']
        for trade in data:
            tData.append(
                {
                    'price': trade['price'],
                    'qty': trade['size'],
                    'quoteQty': float(
                        trade['price']) *
                    float(
                        trade['size']),
                    'isBuyerMaker': trade['side'] == 'Buy',
                    'blockTrade': trade['isBlockTrade']})
        return tData  # 对齐币安格式

    # 最新币价
    def tickers(self, symbol):
        params = self._rtParams(symbol)
        data = self._ccxt.publicGetV5MarketTickers(params)["result"]['list'][0]
        data['price'] = data['lastPrice']
        del data['lastPrice']
        # > lastPrice	string	最新市場成交價
        # > indexPrice	string	指數價格
        # > markPrice	string	標記價格
        # > prevPrice24h	string	24小時前的整點市價
        # > price24hPcnt	string	市場價格相對24h前變化的百分比
        # > highPrice24h	string	最近24小時的最高價
        # > lowPrice24h	string	最近24小時的最低價
        # > prevPrice1h	string	1小時前的整點市價
        # > openInterest	string	未平倉合約的數量
        # > openInterestValue	string	未平倉合約的價值
        # > turnover24h	string	最近24小時成交額
        # > volume24h	string	最近24小時成交量
        # > fundingRate	string	資金費率
        # > nextFundingTime	string	下次結算資金費用的時間 (毫秒)
        # > predictedDeliveryPrice	string	預計交割價格. 交割前30分鐘有值
        # > basisRate	string	交割合約基差率
        # > basis	string	交割合約基差
        # > deliveryFeeRate	string	交割費率
        # > deliveryTime	string	交割時間戳 (毫秒), 僅適用於交割合約
        # > ask1Size	string	買1價的數量
        # > bid1Price	string	買1價
        # > ask1Price	string	賣1價
        # > bid1Size	string	買1價的數量
        return data
