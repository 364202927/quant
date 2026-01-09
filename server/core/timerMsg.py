from server.utils import evtConnect, evtFireAsync, eTimeTs, kEvt_GetTime, kEvt_Time, log
from datetime import datetime,timedelta
import asyncio,heapq
kMaxSleepTime = 60  # 最大休眠时间60秒

class schedule:
    def __init__(self, timeKey):
        self.__pool = []  # 任务ID列表
        self.__timeKey = timeKey
        self.__interval = float(timeKey[:-1]) * eTimeTs[timeKey[-1]] # 间隔时间
        # print("~~~~interval~~~~",self.__interval,float(timeKey[:-1]),eTimeTs[timeKey[-1]])
        # exit()
        self.__nextRun = self._nextTime()
        # log(f"Schedule初始化:",timeKey,datetime.now().strftime('%m-%d %H:%M:%S'),'  next:',self.__nextRun.strftime('%m-%d %H:%M:%S'))

    def _nextTime(self,t = datetime.now()):
        return t + timedelta(seconds=self.__interval)

    def next(self):
        return self.__nextRun

    async def update(self):
        if not self.__pool:
            return
        # 触发时间事件
        begin = datetime.now()
        await evtFireAsync(kEvt_GetTime, self.__timeKey, self.__pool.copy())
        end = datetime.now()
        # 计算下一次触发时间
        if end > self._nextTime(begin) : #处理卡顿的情况
            self.__nextRun = self._nextTime(datetime.now())
            print("~~~~判断大于15分钟补触发一次(这里暂时先不管)~~~~",end, self._nextTime(begin))
            return
        self.__nextRun = self._nextTime(begin)
        # print("~~evt~~~~~",self.__timeKey, datetime.now().strftime("%m-%d %H:%M:%S"),'  next:',self.__nextRun.strftime('%m-%d %H:%M:%S'))

    def pushId(self, taskId):
        if taskId not in self.__pool:
            self.__pool.append(taskId)

    def __lt__(self, other):
        return self.__nextRun < other.__nextRun

class timerMgr:
    """异步时间管理器"""

    def __init__(self):
        self.__heap = []        # 最小堆，存储 schedule 对象
        self.__schedules = {}   # 存储 schedule 对象引用 { '1m': scheduleObj, ... }
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
        taskId = args[0]
        timeKeys = args[1]
        if not isinstance(timeKeys, list):
            timeKeys = [timeKeys]
        for tk in timeKeys:
            self.addSchedule(tk, taskId)

    async def run(self):
        if not self.__heap:
            return

        # 取出栈顶的进行休眠
        sch = self.__heap[0]
        restTime = (sch.next() - datetime.now()).total_seconds()
        if restTime > 0:
            sleep_time = min(restTime, kMaxSleepTime)
            await asyncio.sleep(sleep_time)
        now = datetime.now()
        if sch.next() > now:
            return
        # 触发任务
        sch = heapq.heappop(self.__heap)
        await sch.update()
        heapq.heappush(self.__heap, sch)

    def show(self):
        print('\n=======定时器列表 (Heap)=====')
        sorted_heap = sorted(self.__heap)
        for sch in sorted_heap:
            print(f"  {sch}")
        print('==================\n')