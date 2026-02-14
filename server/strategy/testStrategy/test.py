from server.strategy.base.testCTA import *
# from server.utils import pdData, log
# from datetime import datetime

class test(testCTA):
    "测试用法"

    _kLinePd = None  # 原始数据

    def info(self):
        return "demo+测试代码"

    def init(self):
        self.regTime('1s', "1m")
        # 初始化指标
        self.regIndicators({'candles':'other.kLine',
                            'vwap':'volume.vwap',
                            'boll':'oscillators.boll'})
        
        info("~~~~init test~~~~")
        # 指标合并计算
        # self.candles.delimit(exName = 'binanceMain',symbols = ['spot_BTCUSDT','swap_BTCUSDT'])
        # candles = self.candles.calculate(self.vwap, self.boll)
        # print("~~~spot_BTCUSDT~~~~~\n",candles['spot_BTCUSDT'].get())
        # print("~~~swap_BTCUSDT~~~~~\n",candles['swap_BTCUSDT'].get())    
        # 获取历史数据
        # kLine = self.candles.historyCandles(symbol = 'spot_BTCUSDT', seTime = ['2020-1-01 00:00:00','2020-05-01 00:00:00'], timeFrame = '15m')
        # print("~~~historyCandles 15m~~~~~\n",kLine.get())


    def update_1sLess(self, id, timeKey):
        # cta = self.getCTA('test')
        # print("~~evt_1sLess~~~~~",timeKey, datetime.now().strftime("%m-%d %H:%M:%S"))
        pass

    def update_1s(self, id, timeKey):
        # cta = self.getCTA('test')
        
        # log("~~evt_1s~~~~~",timeKey)
        # print("~~evt_1s~~~~~s",timeKey,datetime.now().strftime("%m-%d %H:%M:%S"))
        pass


    def update_1m(self, id,timeKey):
        # print("~~evt_1m~~~~~",timeKey,datetime.now().strftime("%m-%d %H:%M:%S"))
        pass
