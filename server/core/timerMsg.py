from server.utils import evtConnect, evtFireAsync, eTimeTs, kEvt_GetTime, kEvt_Time, log,timeFrame2Float
from datetime import datetime,timedelta
import asyncio,heapq
kMaxSleepTime = 60  # 最大休眠时间60秒

class schedule:
    def __init__(self, timeKey):
        def _parseTime(s: str): #日期转换
            now = datetime.now()
            if ':' not in s:
                return now, s
            data, interval = s.split(":")  
            beginData = now
            parts = data.strip().split()
            if len(parts) == 2:
                month, day = map(int, parts[0].split('-'))
                hour = int(parts[1])
                beginData = datetime(now.year, month, day, hour, 0, 0)
            elif len(parts) == 1:
                month = now.month
                day = now.day
                hour = int(parts[0])
                beginData = datetime(now.year, month, day, hour, 0, 0)
            return beginData, interval
        #
        self.__pool = []  # 任务ID列表
        self.__timeKey = timeKey
        # print("~~~schedule init~~~~",timeKey, _parseTime(timeKey))
        beginData,interval = _parseTime(timeKey) #开始时间,间隔
        self.__interval = timeFrame2Float(interval) # 间隔时间转换
        # print("~~~~interval~~~~",self.__interval,float(timeKey[:-1]),eTimeTs[timeKey[-1]])
        self.__nextRun = self._nextTime(beginData)
        # log(f"Schedule::",timeKey, '  ',datetime.now().strftime('%m-%d %H:%M:%S'),'  next=',self.__nextRun.strftime('%m-%d %H:%M:%S'))

    #下次触发时间
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
    """时间管理器"""

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