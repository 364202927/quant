from server.strategy.base.testCTA import *


class test(testCTA):
    "测试用法"

    _kLinePd = None  # 原始数据

    def info(self):
        return "demo+测试代码"

    def init(self):
        self.symbol = ['swap_BTCUSDT']  # todo:应该可以不要
        self.tacticsTime = ['1s', "1m"]
        # 获取原始数据
        self._kLinePd = pdData()
        self._kLinePd.readFile('binance_BTCUSDT.pkl')
        # self._kLinePd.resample("15m",['2019-01-01 00:00:00','2020-01-01 00:00:00'])
        # self._kLinePd.resample("D")
        # 初始化指标
        # self.regStrategy({'boll':'oscillators.boll',
        # 'boll2':'timings.boll',
        # 'vwap':'volume.vwap'})
        # self.boll.delimit(maDay= 30, stdev = 2.5)
        # self.boll.calculate(self._kLinePd.get())
        # print("~~~~boll~~~~", self._kLinePd.get(),self.boll.get())
        # newPf = pdData()
        # newPf.pfMerge([self._kLinePd.get(),self.boll.get()])
        # newPf.setPf(self.bollSig1(newPf.get()), 'signal', ['std', 'dis'])

        print("~~~~init test~~~~")
        log(self._kLinePd.get())

    def update_1s(self, id):
        # cta = self.getCTA('test')
        print("~~evt_1s~~~~~")
