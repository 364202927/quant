from server.strategy.base.contractCTA import *
from server.strategy.base.realTrade import *
from server.utils import log

class testTrade(contractCTA, realTrade):
    "交易所api测试调用"

    def __init__(self):
        super().__init__()
        realTrade.__init__(self)
        self.bInit = False
        self._testStep = 0
     
    def info(self):
        return "demo+k线数据,交易所成交"

    def init(self):
        self.regTime('01:1d', "10s")    #注册时间 1.每天1点 2.每分钟
        self.settingTrade('binanceMain') #默认下单设置
        # 初始化指标
        self.regIndicators({'candles':'other.kLine',
                            'vwap':'volume.vwap',
                            'boll':'oscillators.boll'})
        print("~~~~init test~~~~")
        # self.pause()                     #不激活策略,定时器和回测 会忽略该策略
        # 指标获取and合并
        self.candles.delimit(exName = 'binance', symbols = ['spot_BTCUSDT','swap_BTCUSDT'])
        # candles = self.candles.getCandles('spot_BTCUSDT',[])
        # candles = self.candles.calculate(self.vwap, self.boll)
        # print("~~~spot_BTCUSDT~~~~~\n",candles.get())
        # print("~~~swap_BTCUSDT~~~~~\n",candles['swap_BTCUSDT'].get())
        # 获取历史数据
        # kLine = self.candles.historyCandles(symbol = 'spot_BTCUSDT', seTime = ['2020-1-01 00:00:00','2020-05-01 00:00:00'], timeFrame = '15m')
        # print("~~~historyCandles 15m~~~~~\n",kLine.get())
        
        # history = self.historyOrders([swapU('BTC/USDT')])
        # history = self.historyOrders([spot('DOGE/USDT')])
        # logFormat(history)


    def update_10s(self, id, timeKey):
        if self.bInit: return
        if self._testStep == 0:
            log("~~~~~~test初始化完成~~~~~~~~")
        #现货
        if self._testStep == 0:
            self.buy('DOGE/USDT', totelPrice = 1)                           #市价买入1u,如totelPrice少于最少下单按最少下单
        elif self._testStep == 1:
            self.buy('DOGE/USDT', totelPrice = 'bet:1')                                 #以现货总仓位的10%,挂单最优价买入
        elif self._testStep == 2:
            self.buy('DOGE/USDT', totelPrice = 1, price = 0.07)             #挂单价0.007,总单价1u
        elif self._testStep == 3:
            self.cencel(spot('DOGE/USDT'))                                  #取消挂单
        elif self._testStep == 4:
            self.sell('DOGE/USDT')                                          #默认全卖
            self.bInit = True
        
        #合约
        if self._testStep == 0:
            # self.openLong(swapU('DOGE/USDT'), totelPrice = 5,price = 0.07,lv=2)
            self.openLong(swapU('DOGE/USDT'), totelPrice = 5)
        elif self._testStep == 1:
            # self.openShort(swapU('DOGE/USDT'), totelPrice = 5,price = 0.1)
            self.openShort(swapU('DOGE/USDT'), totelPrice = 5,isMarket= True)
            # pass
        elif self._testStep == 2:
            # self.openShort(futureU('ETH/USDT', timeIndex = 1), totelPrice = 1)
            pass
        elif self._testStep == 3:
            self.cencel(swapU('DOGE/USDT'))                                      #取消挂单
            # self.cencel(futureU('ETH/USDT', timeIndex = 1))                       #取消季单
        elif self._testStep == 4:
            self.closePos(swapU('DOGE/USDT'),dir=kLong,isMarket=True)
            self.closePos(swapU('DOGE/USDT'),dir=kShort,isMarket=True)
            # self.closePos(futureU('ETH/USDT', timeIndex = 1),dir=kShort)
            self.bInit = True
        
        log("~~~Step~~~~",self._testStep)
        self._testStep += 1
