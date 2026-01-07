from server.strategy.base.baseCTA import *
from server.utils.logger import log

class testCTA(baseCTA):
    "测试模式"

    __testData = None
    __testCount, __closeCount = 0, 0
    __testOrders, __openl, __opens = [], [], []

    # def __init__(self, fnCta):
    #     super().__init__(fnCta)
    # print("~~~~",self._maxLimit)
    # def init(self):
    #     self._testMode()

    # todo:改成
    # def evtProcess(self, key, *args):
    # super().evtProcess(key, *args)
    def _processCount(self):
        pass
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

    def _testMode(self, pdData, startCount=100, closeCount=-1):  # 模拟实时获取k线,每隔0.2秒返回一条新数据
        self.__testMode = True
        self.__testCount = startCount
        self.__testData = pdData
        self.__closeCount = closeCount
        if closeCount == -1:
            self.__closeCount = len(pdData.get())
        self.tacticsTime = ['0']

    # 测试模式开仓
    def testOpen(self, longFn, shortFn, mark=''):  # mark:开仓标记
        def open(dir):
            pos = longFn() if dir == 'long' else shortFn()
            if pos == 0:
                return False
            # print("~~~~~~open~~~",dir,pos)
            open_dir = self.__openl if dir == 'long' else self.__opens
            open_dir.append(
                {'mark': mark, 'idx': self.__testCount - 1, 'position': pos})
            return True
        # logic
        if not open('long'):
            return open('short')
        return False
    # 测试模式平仓

    def testClose(self, longFn, shortFn):
        def close(dir):
            open_dir = self.__openl if dir == 'long' else self.__opens
            if len(open_dir) > 0:
                pos = longFn() if dir == 'long' else shortFn()
                if pos == 0:
                    return False
                # print("~~~~~~close~~~",dir,pos)
                mark = open_dir[0]['mark']
                open_dir.append(
                    {'mark': mark, 'idx': self.__testCount - 1, 'position': pos})
                # 仓位百分比为100完全平仓
                if abs(pos) == 100:
                    self.__testOrders.append(
                        {'dir': 1 if dir == 'long' else -1, 'mark': mark, 'position': open_dir})
                    if dir == 'long':
                        self.__openl = []
                    else:
                        self.__opens = []
                return True
        #
        if not close('long'):
            return close('short')
        return False
    # 测试模式返回仓位

    def testPosition(self, dir):
        open_dir = self.__openl if dir == 'long' else self.__opens
        if len(open_dir) > 0:
            return open_dir[0]['idx']
        return 0

    # 继承,测试函数
    def testSignal(self, pf, count): pass  # 信号
    def testEnd(self, orders): pass  # 测试结束
    def evtTime(self, timeKey): pass  # 时间事件统一接收
