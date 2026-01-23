from server.strategy.base.testCTA import *
# from server.utils import pdData, log
from datetime import datetime

class test(testCTA):
    "测试用法"

    _kLinePd = None  # 原始数据

    def info(self):
        return "demo+测试代码"

    def init(self):
        self.regTime('0.5s', '1s', "1m")
        # 获取原始数据
        self._kLinePd = pdData()
        self._kLinePd.readFile('binance_BTCUSDT.pkl')
        # self._kLinePd.resample("15m",['2019-01-01 00:00:00','2020-01-01 00:00:00'])
        # self._kLinePd.resample("D")
        # 初始化指标
        self.regIndicators({'boll':'oscillators.boll',
                            'vwap':'volume.vwap'})


        # self.boll.delimit(maDay= 30, stdev = 2.5)
        # self.boll.calculate(self._kLinePd.get())
        # print("~~~~boll~~~~", self._kLinePd.get(),self.boll.get())
        # newPf = pdData()
        # newPf.pfMerge([self._kLinePd.get(),self.boll.get()])
        # newPf.setPf(self.bollSig1(newPf.get()), 'signal', ['std', 'dis'])
        
        print("~~~~init test~~~~",datetime.now().strftime("%m-%d %H:%M:%S"))
        # log(self._kLinePd.get())

    def update_1sLess(self, id, timeKey):
        # cta = self.getCTA('test')
        # print("~~evt_1sLess~~~~~",timeKey, datetime.now().strftime("%m-%d %H:%M:%S"))
        pass

    def update_1s(self, id,timeKey):
        # cta = self.getCTA('test')
        # print("~~evt_1s~~~~~",timeKey,datetime.now().strftime("%m-%d %H:%M:%S"))
        pass
    def update_10s(self, id):
        # cta = self.getCTA('test')
        # print("~~evt_10s~~~~~",datetime.now().strftime("%m-%d %H:%M:%S"))
        pass


    def update_1m(self, id):
        # print("~~evt_1m~~~~~",datetime.now().strftime("%m-%d %H:%M:%S"))
        pass
