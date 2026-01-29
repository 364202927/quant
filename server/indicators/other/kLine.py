import time
from indicators.baseIndicators import *
from server.utils import diff_Pdtime,reviseTime

class kLine(baseIndicators):
    '整理k线'

    def init(self):
        self._ex = None  # 交易所
        self._symbols = {}  # 交易对

    def delimit(self, **kwargs) -> None:
        self._ex = kwargs.get('ex', self._ex)
        self._symbols = kwargs.get('stDev', self._symbols)

    def calculate(self):
        pass
    def calculateTa(self, pd:pdData):pass
   
    # def repairKline(self, symbol, fileName):
    #     return 0

    # #
    # def ticker(self, symbol, timeframe='5m'):  # todo:不要
    #     return self.ex.ticker(symbol, timeframe)
    

    # 获取币种历史 (spot现货，swap永续，future期权) , [开始,结束时间], 时间粒度, 保存到文件
    def getHistoryCandles(self, symbol, seTime, timeframe='5m', fileType=""):
        # pd = pdData()
        # pf = self.getKline(symbol, seTime)
        # pd.setPf(pf)
        # allData = [pf]
        # # 判断是否必要再获取
        # diff_seconds = diff_Pdtime(pd.get(-1, 0))
        # if diff_seconds < 5:
        #     return pd.get()

        # print("开始从交易所获取k线")
        # while 1:
        #     isSeq = pd.get(0, 0) < pd.get(-1, 0)
        #     startTime = isSeq and pd.get(-1, 0) or pd.get(0, 0)
        #     end = startTime
        #     pf = self.getKline(symbol, [str(startTime), str(seTime[1])])
        #     pd.setPf(pf)
        #     allData.append(pf)
        #     print(">>k线数量:", pf.shape[0], "  时间：",end, "~", reviseTime(seTime[1], -10))
        #     if self._maxLimit > pf.shape[0] or end >= reviseTime(
        #             seTime[1], -10):
        #         break
        #     time.sleep(0.1) #这里需要暂停一下,
        # pd.format(allData, style='concat')
        # if fileType != "":  # 保存到文件
        #     pd.save2File(self.name() + "_" + symbol + fileType)
        # if timeframe != '5m':  # 时间粒度
        #     pd.resample(timeframe)
        # return pd.get()
        pass
