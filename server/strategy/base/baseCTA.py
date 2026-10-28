from server.utils import pdData, require, err, warn, info, log, spot, swapU, swapC, futureU, futureC, getRootName, slit, str2time,openWeb
from server.market import kLong, kShort, kSwap, kFuture, kDelivery, kSpot, kBuy, kSell
from server.core.task import taskHandle
kIndicatorsFile = 'server.indicators.'
# todo:定时器暂时没测试

class baseCTA(taskHandle):
    "交易基类"

    def regIndicators(self, dict):
        dictIndicator = {}
        for name, indicatorName in dict.items():
            indicator = require(kIndicatorsFile + indicatorName)()
            setattr(self, name, indicator)
            dictIndicator[name] = indicator
        #保存指标到共享
        self.indicators[self.name()] = dictIndicator

    # 初始化
    def init(self): pass

    # 接收时间回调
    # def stopProcess(self) 任务被设为停止时，只会触发停止回调
    # def process(tabId, timeKey) 在所有时间前调用,retrun true后续不再触发其余时间回调
    # def update_(timeKey)(tabId, timeKey) 正常时间回调
    # def update_1sLess(tabId, timeKey) 少于1秒
