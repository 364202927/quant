from server.utils import evtConnect, evtReturn, kEvt_GetTime, kEvt_Time, timeFrame2Float, evtFire
from datetime import datetime, timedelta
import asyncio, heapq
kMaxSleepTime = 60  # 最大休眠时间60秒

class schedule:
    def __init__(self, timeKey):
        def _parseTime(s: str): #日期转换,返回(起始时间, 间隔字符串)
            now = datetime.now()
            if ':' not in s:
                return now, s
            data, interval = s.split(":", 1)
            parts = data.strip().split()
            if len(parts) == 2:
                month, day = map(int, parts[0].split('-'))
                hour = int(parts[1])
            elif len(parts) == 1:
                month, day = now.month, now.day
                hour = int(parts[0])
            else:
                return now, interval
            return datetime(now.year, month, day, hour, 0, 0), interval
        #
        self.__pool = []  # 任务ID列表
        self.__timeKey = timeKey
        beginData, interval = _parseTime(timeKey) #开始时间,间隔
        self.__interval = timeFrame2Float(interval) # 间隔时间转换
        self.__nextRun = self._nextTime(beginData)

    #下次触发时间
    def _nextTime(self, t=None):
        if t is None:
            t = datetime.now()
        return t + timedelta(seconds=self.__interval)

    def next(self):
        return self.__nextRun

    async def update(self):
        if not self.__pool:
            return True
        # 触发时间事件
        begin = datetime.now()
        evtFire(kEvt_GetTime, self.__timeKey, self.__pool.copy())
        end = datetime.now()
        # 计算下一次触发时间
        if end > self._nextTime(begin): #处理卡顿的情况:触发耗时过长则以当前时刻重新计时,不追赶错过的次数
            self.__nextRun = self._nextTime(datetime.now())
            return True
        self.__nextRun = self._nextTime(begin)
        return True

    def pushId(self, taskId):
        if taskId not in self.__pool:
            self.__pool.append(taskId)

    def __lt__(self, other):
        return self.__nextRun < other.next()

    def __repr__(self):
        return f"{self.__timeKey} next={self.__nextRun.strftime('%m-%d %H:%M:%S')} tasks={self.__pool}"

class oneShot:
    def __init__(self, taskId: object, timeKey: str) -> None:
        self.taskId = taskId
        self.timeKey = timeKey
        self.__interval = timeFrame2Float(timeKey)
        self.__nextRun = datetime.now() + timedelta(seconds=self.__interval)

    def next(self) -> datetime:
        return self.__nextRun

    async def update(self) -> bool:
        result = evtReturn(kEvt_GetTime, 'storageSubscribe', self.taskId, self.timeKey)
        if result is True:
            return False
        self.__nextRun = datetime.now() + timedelta(seconds=self.__interval)
        return True

    def __lt__(self, other: object) -> bool:
        return self.__nextRun < other.next()

    def __repr__(self) -> str:
        return f"once:{self.taskId} {self.timeKey} next={self.__nextRun.strftime('%m-%d %H:%M:%S')}"

class timerMgr:
    """时间管理器"""

    def __init__(self):
        self.__heap = []        # 最小堆，存储 schedule 对象
        self.__schedules = {}   # 存储 schedule 对象引用 { '1m': scheduleObj, ... }
        self.__oneShots = {}    # 单次定时器去重表 { (id, timeKey): oneShot }
        evtConnect(kEvt_Time, self)  # 注册事件接收

    def addSchedule(self, timeKey, taskId):
        if timeKey not in self.__schedules:
            objSchedule = schedule(timeKey)
            self.__schedules[timeKey] = objSchedule
            heapq.heappush(self.__heap, objSchedule)
        self.__schedules[timeKey].pushId(taskId)

    def evtProcess(self, key, *args):
        if len(args) < 2:
            return
        taskId, timeKeys = args[0], args[1]
        loop: bool = args[2] if len(args) > 2 else True
        if not isinstance(timeKeys, list):
            timeKeys = [timeKeys]
        if not loop:
            if any((taskId, tk) in self.__oneShots for tk in timeKeys):
                return
            for tk in timeKeys:
                timer = oneShot(taskId, tk)
                self.__oneShots[(taskId, tk)] = timer
                heapq.heappush(self.__heap, timer)
            return
        for tk in timeKeys:
            self.addSchedule(tk, taskId)

    async def run(self):
        if not self.__heap:
            await asyncio.sleep(1)
            return
        # 取出栈顶的进行休眠
        sch = self.__heap[0]
        restTime = (sch.next() - datetime.now()).total_seconds()
        if restTime > 0:
            sleep_time = min(restTime, kMaxSleepTime)
            await asyncio.sleep(sleep_time)
        # 重新取堆顶（sleep 期间可能有更早的任务插入）
        sch = self.__heap[0]
        if sch.next() > datetime.now():
            return
        # 触发任务
        sch = heapq.heappop(self.__heap)
        keep = await sch.update()
        if keep:
            heapq.heappush(self.__heap, sch)
        elif isinstance(sch, oneShot):
            self.__oneShots.pop((sch.taskId, sch.timeKey), None)

    def show(self):
        print('\n=======定时器列表 (Heap)=====')
        for sch in sorted(self.__heap):
            print(f"  {sch}")
        print('==================\n')
