from server.strategy.base.contractCTA import *
from server.strategy.base.realTrade import *
# from server.utils import pdData, log
# from datetime import datetime
import time

class test(contractCTA, realTrade):
    "交易所api测试调用"

    def info(self):
        return "demo+k线数据,交易所成交"

    def init(self):
        self.regTime('01:1d', "1m")    #注册时间 1.每天1点 2.每分钟
        self.settingTrade(exName=['binanceMain'], def_lv = 1) #默认下单设置
        # 初始化指标
        self.regIndicators({'candles':'other.kLine',
                            'vwap':'volume.vwap',
                            'boll':'oscillators.boll'})
        print("~~~~init test~~~~")
        self.pause()
        # 指标合并计算
        # self.candles.delimit(exName = 'binanceMain',symbols = ['spot_BTCUSDT','swap_BTCUSDT'])
        # candles = self.candles.calculate(self.vwap, self.boll)
        # print("~~~spot_BTCUSDT~~~~~\n",candles['spot_BTCUSDT'].get())
        # print("~~~swap_BTCUSDT~~~~~\n",candles['swap_BTCUSDT'].get())
        # 获取历史数据
        # kLine = self.candles.historyCandles(symbol = 'spot_BTCUSDT', seTime = ['2020-1-01 00:00:00','2020-05-01 00:00:00'], timeFrame = '15m')
        # print("~~~historyCandles 15m~~~~~\n",kLine.get())
        
        #现货
        # self.buy('DOGE/USDT', totelPrice = 1)                            #市价买入1u,如totelPrice少于最少下单按最少下单
        # time.sleep(10)
        # self.buy('DOGE/USDT', totelPrice = 'bet:10', orderBook=0)        #以现货总仓位的10%,挂单最优价买入
        # time.sleep(10)
        # self.buy('DOGE/USDT', totelPrice = 1, price = 0.07)               #挂单价0.07,总单价1u
        # time.sleep(10)
        # self.cencel('DOGE/USDT')
        # self.sell('DOGE/USDT')                                            #默认全卖
        # time.sleep(10)
        #合约
        # self.openLong(swapU('DOGE/USDT'), totelPrice = 'bet:5',price = 0.07,lv=2)      #u本位永续,bet:10是总仓位的10%
        # self.openLong(swapU('DOGE/USDT'), totelPrice = 1)
        # time.sleep(20)
        # self.openShort(swapU('DOGE/USDT'), totelPrice = 1,isMarket=True)                #市价买入(立即吃单)
        # time.sleep(20)
        # self.openShort(futureU('BTC/USDT', timeIndex = 1), totelPrice = 1)              #u本位交割开空
        # self.closePos(swapU('DOGE/USDT'),dir=kLong)
        # self.closePos(swapU('DOGE/USDT'),dir=kShort)
        # self.closePos(swapU('DOGE/USDT'),dir='open')
        
        # history = self.historyOrders([swapU('BTC/USDT')])
        # history = self.historyOrders([spot('DOGE/USDT')])
        # logFormat(history)


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
