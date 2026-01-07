import abc
from server.utils import pdData, log, warn, require, evtFire, kEvt_ModifiedTime, eTaskState
from server.core.task import task
from server.indicators import baseIndicators

# 导入 task 模块的所有内容（保持向后兼容）
from server.core.task import *

# ? 1、是否保存状态
# ? 2、调用次数
kIndicatorsFile = 'indicators.'


class baseCTA(task, metaclass=abc.ABCMeta):
    "基类模版"

    # __testMode = False  #开启后用updata_test(pf,count)接收数据
    # __testData = None
    # __testCount, __closeCount = 0,0
    # __testOrders,__openl,__opens = [],[],[]

    # 事件处理
    def evtProcess(self, key, *args):
        if (self.state() == eTaskState.get('eActive')):
            return
        timeKey = args[0]
        tabId = args[1]
        # 过滤只触发接收的时间戳
        filter = set(self.tacticsTime)
        if timeKey not in filter:
            return
        # print('evtProcess',self.tacticsTime, timeKey)
        # testMode
        # if self.__testMode:
        #     self.__testCount += 1
        #     kline = self.__testData.getHead(self.__testCount)
        #     start = self.__testCount - 100
        #     if start < 0: start = 0
        #     self.testSignal(kline[start:self.__testCount], self.__testCount)
        #     if self.__testCount >= self.__closeCount:
        #         self.testEnd(self.__testOrders)
        #         # exit()
        #     return
        self._processCount()
        # 调用evt fn:  update_ts
        fnName = 'update_' + timeKey
        if hasattr(self, fnName):
            fnEvt = getattr(self, fnName)
            fnEvt(tabId)
            return
        warn('当前时间事件未接收:', fnName)
        self.evtTime(timeKey)

    # 改变策略时间
    def setTacticsTime(self, tabTime):
        self.tacticsTime = tabTime
        evtFire(kEvt_ModifiedTime, self.get('id'), tabTime)
    # 注册策略 dict = {name:指标, ...}

    def regStrategy(self, dict):
        # def callFn(indicatorName,signal):
        #     self.evtProcess(kEvt_Signal, 0, self.get('id'), indicatorName, signal)
        for name, indicatorName in dict.items():
            indicator = require(kIndicatorsFile + indicatorName)  # (callFn)
            self.indicators[name] = indicator
            setattr(self, name, indicator)

    # 测试模式
    # def testMode(self, pdData, startCount = 100, closeCount = -1):#模拟实时获取k线,每隔0.2秒返回一条新数据
    #     self.__testMode = True
    #     self.__testCount = startCount
    #     self.__testData = pdData
    #     self.__closeCount = closeCount
    #     if closeCount == -1:
    #         self.__closeCount = len(pdData.get())
    #     self.tacticsTime = ['0']
    # #测试模式开仓
    # def testOpen(self, longFn, shortFn, mark = ''):#mark:开仓标记
    #     def open(dir):
    #         pos = longFn() if dir == 'long' else shortFn()
    #         if pos == 0: return False
    #         # print("~~~~~~open~~~",dir,pos)
    #         open_dir = self.__openl if dir == 'long' else self.__opens
    #         open_dir.append({'mark':mark, 'idx':self.__testCount - 1, 'position':pos})
    #         return True
    #     #logic
    #     if not open('long'):
    #         return open('short')
    #     return False
    # #测试模式平仓
    # def testClose(self, longFn, shortFn):
    #     def close(dir):
    #         open_dir = self.__openl if dir == 'long' else self.__opens
    #         if len(open_dir) > 0:
    #             pos = longFn() if dir == 'long' else shortFn()
    #             if pos == 0: return False
    #             # print("~~~~~~close~~~",dir,pos)
    #             mark = open_dir[0]['mark']
    #             open_dir.append({'mark':mark,'idx':self.__testCount - 1, 'position':pos})
    #             #仓位百分比为100完全平仓
    #             if abs(pos) == 100:
    #                 self.__testOrders.append({'dir':1 if dir == 'long' else -1, 'mark':mark, 'position':open_dir})
    #                 if dir == 'long':
    #                     self.__openl = []
    #                 else:
    #                     self.__opens = []
    #             return True
    #     #
    #     if not close('long'):
    #         return close('short')
    #     return False
    # #测试模式返回仓位
    # def testPosition(self, dir):
    #     open_dir = self.__openl if dir == 'long' else self.__opens
    #     if len(open_dir) > 0:
    #         return open_dir[0]['idx']
    #     return 0

    # interface
    @abc.abstractmethod  # 初始化
    def init(self): pass
    def _processCount(self): pass
