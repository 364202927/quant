from server.strategy.base.contractCTA import *
from server.strategy.base.realTrade import *
# from server.utils import pdData, log
# from datetime import datetime
import time

class test(contractCTA, realTrade):
    "交易所api测试调用"

    def __init__(self):
        super().__init__()
        realTrade.__init__(self)
        self.bInit = False
     
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

    def update_10s(self, id, timeKey):
        if self.bInit: return
        self.bInit = True
        print("~~~~~~update_10s~~~~~~~~")
        #现货
        self.buy('DOGE/USDT', totelPrice = 1)                            #市价买入1u,如totelPrice少于最少下单按最少下单
        # self.buy('DOGE/USDT', totelPrice = 'bet:10', orderBook=0)      #以现货总仓位的10%,挂单最优价买入 未测试
        # self.cencel('DOGE/USDT')                                        #测单未测试
        # self.sell('DOGE/USDT')







#任务
# 优化:
# web
# 1.每次切换进入页面时刷新到初始状态
# 2.web添加load画面(中间刷新图标在旋转),load过程全页面阻挡不能点击
# 3.webapp初始化时,app会调用2次init
# 4.优化页面布局
# 后端
# 1.task1 逻辑优化修改,task2指标优化检测
# 2.检测所有核心代码的async是否成功,询问该框架和成熟的金融框架有什么区别，那些不足需要完善的
# 3.回测系统优化为run没有未来数据,web添加快速测试按钮
# 4.绑定交易所时添加risk(0~5,默认0管),有risk会进入风控 管控进行平仓操作
# 5.ws 开始监听 才发送init对task进行初始化调用,task.init,等所有初始化完成后再调用(run)
# 2.oms拆分订单要维护一个id,所有子订单完成时才会策略发送完成事件

# 任务:
# 0.框架(不一样的风格（进取，中等，保守）)
# 1.日志系统还没做 web+后端
# 2.资产页面
# 3.行情页面
# 4.策略管理页面
# 5.订单管理页面
# 6.完成第一个双均线策略
# 7.完成监控更新币种
# 8,添加最重要交易量oi和cvd指标
# 2.成交历史和深度数据的修改
# 3.缓存优化,每天切分数据


# #优先任务整理
# 1.优先调通下单 现货买卖   合约买卖  撤单
# 2.orders需要记录task的下单信息,现货记录到历史(订单确认后),合约记录到持仓