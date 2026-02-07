import abc
from server.utils import pdData, log, require,err,warn,info
from server.core.task import taskHandle
kIndicatorsFile = 'server.indicators.'

#todo:日志支持

class baseCTA(taskHandle):
    "交易基类"

    def regIndicators(self, dict):
        dictIndicator = {}
        for name, indicatorName in dict.items():
            indicator = require(kIndicatorsFile + indicatorName)()
            setattr(self, name, indicator)
            dictIndicator[name] = indicator
        #保存指标到共享
        self.indicators[self.className()] = dictIndicator

    # 初始化
    @abc.abstractmethod
    def init(self): pass

    # 接收时间回调
    # def stopProcess(self) 任务被设为停止时，只会触发停止回调
    # def process(tabId, timeKey) 在所有时间前调用,retrun true后续不再触发其余时间回调
    # def update_(timeKey)(tabId, timeKey) 正常时间回调
    # def update_1sLess(tabId, timeKey) 少于1秒