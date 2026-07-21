import asyncio
from server.utils import evtConnect, kEvt_Market,kEvt_GetTime, pdData,switchFn,diff_Pdtime,timeFrame2Float,kEvt_Time,evtFire
from server.market import eMarketId,baseExchange


class storageSubscribe:
    "k线/成交历史/深度数据,监听更新"

    def __init__(self):
        self._buffer = {}   # 币安/ok/... = {btc:{kLine:a, depth:b, trades:c}}
        # self._depthLatest: dict[tuple, dict] = {}   # (exName,symbol) -> latest ob
        # self._tradesBuffer: dict[tuple, list] = {}  # (exName,symbol) -> [trade,...]

        self._markets = {}
        self._exMarkets = []    #全交易所
        self._exchanges = {}    #对应交易所,用于获取数据()
        evtConnect(kEvt_Market, self)
        evtConnect(kEvt_GetTime, self)
        evtFire(kEvt_Time, 'subscribe', ['5m'])

    #全交易所初始化
    def setMarket(self, markets):
        self._markets = markets
        self._exMarkets = markets
        self._exchanges = {}
        for ex in self._exMarkets.items():
            exName = ex[1].get('id')
            self._exchanges[exName] = ex[1]

    def evtProcess(self, key, *args):
        if key == 'evtGetTime' and args[1][0] == 'subscribe':
            print("~~~~storageSubscribe 每5m自动更新数据~~~~~", self._markets)
        #
        if key != kEvt_Market: return
        id = args[0]
        def _addscKlne(): #更新订阅数据
            subscribeData = args[1]
            for data in subscribeData.items():
                exKey = data[0]
                if not self._buffer.get(exKey):self._buffer[exKey] = {}
                for symbol in data[1]:
                    if not self._buffer[exKey].get(symbol):
                        self._buffer[exKey][symbol] = {'kLine':None,'depth':None,'trades':None}

        def _getCandles(): #返回k线数据
            exName = args[1]
            symbol = args[2]
            if not self._exchanges.get(exName):return
            pd = self._newestCandles(self._exchanges.get(exName),symbol)
            self._buffer[exName][symbol]['kLine'] = pd
            # print("~~~~save_buffer~~~~~~",self._buffer)
            #todo:一并获取交易量/资金费率/深度
            return pd

        return switchFn({eMarketId['scKline']: _addscKlne,
                        eMarketId['gcKline']: _getCandles,}, 
                        key=id)

    def _updateBuffer(self):
        pass
    
    #返回最新的k线,自动更新到最新
    def _newestCandles(self, ex:baseExchange, symbol: str, timeFrame: str = '5m'):
        pd = self._buffer.get(ex.get('id')).get(symbol).get('kLine') #直接取出保存的数据
        if not pd: #初始化
            fileName = ex.get('id')+'_'+ symbol
            pd = pdData(read = fileName)
            if pd.empty(): #若没有保存的数据,则直接获取最新
                pd.pfConcat(ex.getKline(symbol, [], timeFrame),False)
                return pd
        # 判断数据是否最新
        lastTime = pd.get(-1, 'candle_begin_time')
        if diff_Pdtime(lastTime) < timeFrame2Float(timeFrame):
            return pd
        # print("~~~~文件数据~~~~~~",pd.get(0, 'candle_begin_time'),'~',lastTime)
        #合拼最新数据
        fillPd = ex.getKline(symbol, [lastTime,'now'], timeFrame)
        if fillPd is not None and not fillPd.empty:
            pd.pfConcat(fillPd)
        return pd

    def save2File(self):
        pass
