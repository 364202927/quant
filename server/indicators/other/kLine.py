import time
from server.indicators.baseIndicators import *
from server.utils import diff_Pdtime, reviseTime, log, err,timeFrame2Float,kEvt_Market,evtFire,evtReturn
from server.market import eMarketId
kFileType = '.parquet'


class kLine(baseIndicators):

    def init(self):
        self._exName = None         # 交易所
        self._Pd = None             # 临时记录的k线
        # self.__subscription = {}    # 订阅的交易对

    
    # ex(币安,ok,bybit), symbols:[] 订阅的k线数据
    def delimit(self, exName, symbols: list[str]):
        # if not self._ex:
        #     log(f"获取指标失败,交易所不存在: {exName}")
        #     return
        # # 加载全部交易对K线数据
        # for symbol in symbols:
        #     self._symbols[symbol] = self.newest_kLine(symbol, False)
        # self.__subscription[exName] = symbols
        self._exName = exName
        # self._symbol = symbols
        evtFire(kEvt_Market, eMarketId['scKline'], {exName:symbols})  #订阅k线数据

    def calculate(self, *args: baseIndicators) -> pdData:
        # pdResults = {}
        # #todo:此处可优化:使用pdata.getIndicators()
        # for symbol, pd in self._symbols.items():
        #     pdResults[symbol] = pd
        #     for indicator in args:
        #         pdResults[symbol] = indicator.calculateTa(pdResults[symbol])
        # return pdResults
        # pass
        if self._pd is None or self._pd.raw() is None:
            return None
        pdResults: pdData | pd.DataFrame = self._pd.raw()
        for indicator in args:
            pdResults = indicator.calculateTa(pdResults)
        # Indicators in this project accept/return a mix of DataFrame and
        # pdData.  Normalize only the public result, preserving the wrapper
        # between indicators that require it.
        return pdResults if isinstance(pdResults, pdData) else pdData(
            data=pdResults, style='copy')

    def calculateTa(self,*args: baseIndicators) -> pdData:
        return self.calculate(*args)
    
    # 等待首次缓存完成后返回副本；后续调用直接读取已就绪缓存
    async def getCandles(self, symbol: str, seTime: list,
                         timeFrame: str = '5m', cover: bool = True) -> pdData:
        request = evtReturn(
            kEvt_Market, 'storageSubscribe', eMarketId['gcKline'],
            self._exName, symbol)
        if request is None:
            raise RuntimeError('K线缓存服务未启动')
        candles = await request
        if timeFrame != '5m':
            candles.resample(timeFrame, seTime)
        if cover:
            self._pd = candles
        return candles

    # 返回历史数据,只读取本地文件
    def historyCandles(self, symbol: str, seTime: list,timeFrame: str = '5m', cover: bool = False) -> pdData:
        fileName = self._ex.get('id')+'_'+ symbol
        fullPd = pdData()
        if not fullPd.readFile(fileName, True):
            return fullPd
        if seTime or timeFrame != '5m':
            fullPd.resample(timeFrame, seTime)
        result = pdData(data=fullPd, style='copy')
        if cover:
            self._pd = result
        return result

    # 返回最新的k线cover是否覆盖self._symbols  todo:转移到sub..这里可不要
    # def newest_kLine(self, symbol: str, cover: bool = True) -> pd.DataFrame:
    #     def coverLocal(pd: pdData):
    #         if cover:
    #             self._symbols[symbol] = pd
    #         return pd
    #     # 读取历史数据
    #     timeFrame = '5m'
    #     fileName = self._ex.name()+'_'+ symbol + kFileType
    #     pd = pdData(read = fileName)
    #     if pd.empty():
    #         pd.pfConcat(self._ex.getKline(symbol, [], timeFrame),False)
    #         # pd.save2File(fileName)
    #         return coverLocal(pd)
    #     #文件存在,数据不是最新
    #     lastTime = pd.get(-1, 'candle_begin_time')
    #     # print("~~~~~~~加载到旧数据~~~~~~~~",pd.get())
    #     if diff_Pdtime(lastTime) < timeFrame2Float(timeFrame):#数据是最新的
    #         return coverLocal(pd)
    #     fillPd = self._ex.getKline(symbol, [], timeFrame)
    #     pd.pfConcat(fillPd)
    #     # pd.save2File(fileName)
    #     return coverLocal(pd)
    
    #返回最新的k线,优先加载文件补全最新k线,不存在历史数据只加载最新的
    # def updateSymbol(self, symbol: str, timeframe: str = '5m', limit: int = 100) -> pd.DataFrame:
        # """用最新行情刷新K线，保留最近limit条"""a
        # kData = self._symbols.get(symbol)
        # if not kData:
        #     return pd.DataFrame()
        # newKline = self._ex.getKline(symbol, ['pre5', 'now'], timeframe)
        # tmpPd = pdData()
        # tmpPd.format(newKline, style='candle')
        # kData.pfConcat(tmpPd.get())
        # pf = kData.get()
        # return pf.tail(limit).reset_index(drop=True)

    #只更新最新的K线数据,并合并到self._symbols上
    # def updateSymbols(self) -> None:
        # for symbol in self._symbols.keys():
        #     self.newest_kLine(symbol, True)
        # pass
