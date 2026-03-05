import abc
from server.utils import pdData, require,err,warn,info,log,spot,swapU,swapC,futureU,futureC,getRootName
from server.core.task import taskHandle
from server.utils.fileConfig import g_config, kLogBufType, kOrderBufType, recordBuffer
kIndicatorsFile = 'server.indicators.'

#todo:日志支持

class baseCTA(taskHandle):
    "交易基类"

    def __init__(self):
        super().__init__()
        self._strategy = getRootName(self.__class__, 'strategy')#self._strategyName()
        self._bufOrder:recordBuffer = g_config.get(kOrderBufType)
        print("~~~~~~baseCTA init~~~~", self.className(),self._strategy)

    def regIndicators(self, dict):
        dictIndicator = {}
        for name, indicatorName in dict.items():
            indicator = require(kIndicatorsFile + indicatorName)()
            setattr(self, name, indicator)
            dictIndicator[name] = indicator
        #保存指标到共享
        self.indicators[self.className()] = dictIndicator

    #记录
    def record(self,exName:str, category:str, symbol:str, orderId:int, lv:int, dir:str, orderPrice:int, avgPrice:int, cumQuote:int, fee:int)->str:
        # 下单时间,策略类名,交易所名,币类型,币种,orderId,lv,方向(buy_long),委托价格orderPrice,成交价格avgPrice,总金额cumQuote, 手续费
        # time,strategy,exName,category,symbol,orderId,lv,dir,orderPrice,avgPrice,cumQuote,fee
        tags = {'strategy':self._strategy, 'exName':exName,'category':category, 'symbol':symbol, 'dir':dir}
        return self._bufOrder.push(tags = tags,lv = lv,orderPrice = orderPrice,avgPrice = avgPrice,cumQuote = cumQuote,fee = fee,orderId=orderId,**tags)

    def updateRecord(self, uid, **kwrags):
        self._bufOrder.update(uid,**kwrags)
    
    #当前还在的单子
    def overView(self):
        buff = self._bufOrder.get(strategy = self._strategy)
        print("~~~返回订单记录~~~",buff)
    
    def historyOrders(self):
        # 合并2个订单买入卖出
        pass
    
    # 初始化
    @abc.abstractmethod
    def init(self): pass

    # 接收时间回调
    # def stopProcess(self) 任务被设为停止时，只会触发停止回调
    # def process(tabId, timeKey) 在所有时间前调用,retrun true后续不再触发其余时间回调
    # def update_(timeKey)(tabId, timeKey) 正常时间回调
    # def update_1sLess(tabId, timeKey) 少于1秒