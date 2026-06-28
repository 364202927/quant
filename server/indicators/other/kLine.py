import time
from server.indicators.baseIndicators import *
from server.utils import diff_Pdtime, reviseTime, log, err,timeFrame2Float,utc_now,kEvt_Market,evtFire
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
        evtFire(kEvt_Market, eMarketId['scKline'], {exName:symbols})

    def calculate(self, *args: baseIndicators) -> pdData:
        # pdResults = {}
        # #todo:此处可优化:使用pdata.getIndicators()
        # for symbol, pd in self._symbols.items():
        #     pdResults[symbol] = pd
        #     for indicator in args:
        #         pdResults[symbol] = indicator.calculateTa(pdResults[symbol])
        # return pdResults
        # pass
        if not self._pd: return
        pdResults = self._pd.get()
        for indicator in args:
            pdResults = indicator.calculateTa(pdResults)
        return pdResults

    def calculateTa(self,*args: baseIndicators) -> pdData:
        return self.calculate(args)
    
    # 返回最新的100条k线
    def getCandles(self,symbol: str, seTime: list, timeFrame: str = '5m', cover:bool = True,save2File = True):
        pd = evtFire(kEvt_Market, eMarketId['gcKline'], self._exName, symbol)
        if timeFrame == '5m' and save2File:
            pd.save2File(self._exName+'_'+ symbol + kFileType)
        if timeFrame != '5m':
            pd.resample(timeFrame,seTime)
        if cover:
            self._pd = pd
        return pd

    #返回历史数据
    def historyCandles(self, symbol: str, seTime: list, timeFrame: str = '5m', cover: bool = False) -> pd.DataFrame:
        def rtData(pdata: pdData):
            if cover:
                self._symbols[symbol] = pdata
            if timeFrame != '5m':
                pdata.resample(timeFrame,seTime)
            return pdData(data=pdata, style='copy')
        #默认只保存5分钟周期,超过5分钟从交易所取
        if timeFrame != '5m':
           return pdData(data=self._ex.getKline(symbol, seTime, timeFrame), style='copy')
        #获取历史数据并剪裁
        fileName = self._ex.name()+'_'+ symbol + kFileType
        fullPd = pdData()
        fullPd.readFile(fileName,True)
        fullPd.resample(seTime) 
        timeRange = fullPd.detection(seTime)
        # print("~~~~检查缺失数据~~~~~",len(timeRange),timeRange)
        if len(timeRange) == 0:
            return rtData(fullPd)
        #缺失的值再次从交易所获取
        allData = [fullPd.get()]
        for tr in timeRange:
            # print("~~~~~缺失数据时间范围~~~~~",tr[0], tr[1])
            fixPd = pdData()#从交易所获取时间是原始时区
            kLine = self._ex.getKline(symbol, [tr[0].strftime("%Y-%m-%d %H:%M:%S"), tr[1].strftime("%Y-%m-%d %H:%M:%S")])
            fixPd.format(kLine, style ='copy', utc = utc_now()) #对齐到当前国家时区
            # print("~~~~~补全数据~~~~~",fixPd.get())
            allData.append(fixPd.get())
        history = pdData(style='concat',data=allData)
        # print("~~~~再次检查缺失~~~~~",len(history.detection(timeFrame,seTime)),history.detection(timeFrame,seTime))
        history.save2File(self._ex.name()+'_'+ symbol + kFileType)
        return rtData(history)

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