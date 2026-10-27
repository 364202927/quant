import abc
from server.strategy.base.baseCTA import *
from server.strategy.base.testTrade import *

class testCTA(baseCTA):
    "测试模式: 隔离预知, 策略每根只能看到截止当前bar的K线"

    def __init__(self):
        super().__init__()
        self._trade = testTrade()
        self._pfAll = None          # 全量K线: 回放框架独占, 策略不得读取
        self._kLine = None          # 可见快照: 策略唯一数据入口(每根一个新对象)
        self._cursor = -1            # 已揭示条数 = 当前bar的全局下标+1
        self._startCount = 100
        self._testTimeKey = ''
        self._step = 1

    #增量测试(interval间隔时间触发1次, 首帧startCount条, 之后每次推进step条)
    def _testModel(self,interval=0.1,startCount=100,step = 1):
        self._testTimeKey = str(interval) + 's'
        self.regTime(self._testTimeKey)
        self._startCount = startCount
        self._step = step

    def _loadFile(self,filename,timeframe='5m',stTime=[]):
        self._pfAll = pdData()
        self._pfAll.readFile(filename, True)
        if timeframe != '5m' or len(stTime) > 0:
            # resample 只返回副本不改内部数据,必须回填;stTime 先统一成 UTC0 时间戳(resample 内部把字符串按本地时区解释)
            self._pfAll.format(self._pfAll.resample(timeframe=timeframe,
                                                    seTime=[pdData._normalizeTime(t) for t in stTime],
                                                    offsetUtc=False), style='copy')
        if self._pfAll.empty():
            raise ValueError("回测区间无K线数据:",stTime)

    # 隔离预知: 重置回测数据并揭示 pf[:startCount]; 之后只由 evtTime 推进, 不在这里步进
    def beginTest(self):
        if self._cursor != -1:
            warn("回测运行中, 忽略本次 beginTest")
            return
        if self._pfAll is None or self._pfAll.empty():
            raise ValueError("未加载K线数据, 先调用 _loadFile")
        self._resetTest()
        self._cursor = 0
        self._advance(self._startCount)

    # interval 每触发1次揭示step根K线; 只认自己注册的回放间隔, 避免与实时周期重复推进
    def evtTime(self,timeKey):
        if self._cursor == -1 or timeKey != self._testTimeKey:
            return
        self._advance(self._step)

    # 推进 count 根 -> 决策 -> 已到最后一根时先把结束标记置上, 策略里的 isOver() 才成立
    def _advance(self,count):
        self._reveal(min(self._cursor + count, self._pfAll.size()))
        if self._cursor >= self._pfAll.size():
            self._cursor = -1
        self.startStrategy(self._kLine)

    # 只前进不后退; 快照是 _pfAll 的只读切片(零拷贝), 每根仍是长度固定的新对象
    def _reveal(self,n):
        self._cursor = min(max(self._cursor, n), self._pfAll.size())
        live = self._pfAll.raw().iloc[:self._cursor]
        self._kLine = pdData()
        self._kLine.setHead(live.columns.tolist())
        self._kLine._pf = live

    def isOver(self):
        return self._cursor == -1

    # 回测数据重置点: 策略在这里把账户/持仓/统计恢复到初始状态
    def _resetTest(self):pass

    # 每根新K线调用一次: kLine 只含截止当前bar的数据, 指标需在该快照上自行计算
    @abc.abstractmethod
    def startStrategy(self, kLine):pass