from server.strategy.base.baseCTA import *
# from server.utils import log
# from datetime import date, datetime


class testCTA(baseCTA):
    "测试模式"
    
    def __init__(self):
        super().__init__()
        # print("~~~~~~testCTA __init__~~~~~~~~~")

    #增量测试,每次时间刷新触发k线改变
    def testModel(self,testPd:pdData, startCount=100):
        self.regTime('0.1s')

    #type(contract/spot/stock)合约/现货/股票
    def createTransaction(self, type: str = 'contract') -> None:
        self.trajectories: list[dict] = []
        self.type = type
    def addTransaction(self, dir: str, behavior: str, lv: int, idx: int, position: int) -> None:
        trade = {"behavior": behavior, "pos": idx, "lv": lv, "position%": position}
        # 找同方向最后一条仅有 1 笔的 trajectory（待平仓）
        for item in reversed(self.trajectories):
            if item["dir"] == dir and (len(item["trades"]) > 0 and item["trades"][-1].get('position%')!= 100):
                item["trades"].append(trade)
                return
            
        # 未找到待平仓 → 新开仓 trajectory
        self.trajectories.append({ "dir": dir,"type": self.type, "trades": [trade]})
    
    def getTransaction(self):
        return self.trajectories
    def getTradesCount(self):
        count = 0
        for tra in self.trajectories:
            count += len(tra.get('trades'))
        return count
    
    #web测试开启接口
    @abc.abstractmethod
    def startStrategy(self):pass

   # # 增量测试:对原始数据进行剪裁,每次update发送测试的数据
    # def incrementalTesting(self, pdData, startCount=100, closeCount=-1):  
    #     self.__testCount = startCount
    #     self.__testData = pdData
    #     self.__closeCount = closeCount
    #     if closeCount == -1:
    #         self.__closeCount = len(pdData.get())

    # # 测试模式开仓
    # def testOpen(self, longFn, shortFn, mark=''):  # mark:开仓标记
    #     def open(dir):
    #         pos = longFn() if dir == 'long' else shortFn()
    #         if pos == 0:
    #             return False
    #         # print("~~~~~~open~~~",dir,pos)
    #         open_dir = self.__openl if dir == 'long' else self.__opens
    #         open_dir.append(
    #             {'mark': mark, 'idx': self.__testCount - 1, 'position': pos})
    #         return True
    #     # logic
    #     if not open('long'):
    #         return open('short')
    #     return False
    # # 测试模式平仓
    # def testClose(self, longFn, shortFn):
    #     def close(dir):
    #         open_dir = self.__openl if dir == 'long' else self.__opens
    #         if len(open_dir) > 0:
    #             pos = longFn() if dir == 'long' else shortFn()
    #             if pos == 0:
    #                 return False
    #             # print("~~~~~~close~~~",dir,pos)
    #             mark = open_dir[0]['mark']
    #             open_dir.append(
    #                 {'mark': mark, 'idx': self.__testCount - 1, 'position': pos})
    #             # 仓位百分比为100完全平仓
    #             if abs(pos) == 100:
    #                 self.__testOrders.append(
    #                     {'dir': 1 if dir == 'long' else -1, 'mark': mark, 'position': open_dir})
    #                 if dir == 'long':
    #                     self.__openl = []
    #                 else:
    #                     self.__opens = []
    #             return True
    #     #
    #     if not close('long'):
    #         return close('short')
    #     return False
    # # 测试模式返回仓位
    # def testPosition(self, dir):
    #     open_dir = self.__openl if dir == 'long' else self.__opens
    #     if len(open_dir) > 0:
    #         return open_dir[0]['idx']
    #     return 0
    
    # 继承,测试函数
    # def testSignal(self, pf, count): pass  # 信号
    # def testEnd(self, orders): pass  # 测试结束
    # def evtTime(self, timeKey): pass  # 时间事件统一接收
