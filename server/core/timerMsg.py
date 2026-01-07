import datetime
from server.utils import switchFn, evtConnect, evtFire, eTimeTs, kEvt_GetTime, kEvt_Time, kEvt_ModifiedTime
# from apscheduler.schedulers.background import BackgroundScheduler
# from data.user.shareDate import g_share
# from data.user.center import g_userCenter

# 定时器
# lock = threading.Lock()
# job_defaults = { 'max_instances': 20}#最大支持定时器 个数
# timeScheduler = BackgroundScheduler(timezone= 'Asia/Hong_Kong', job_defaults=job_defaults)
# timeScheduler.start()

# def clearTime(timeKey):
# 	timeScheduler.remove_job(timeKey)


class schedule:
    "触发的时间搓"

    __key = 0  # timeKey, 如1s, 1m, 1h, 1d
    __interval = 0  # timeKey转换后的时间间隔
    __targetTime = 0  # 固定间隔时间
    __isRun = True  # 是否主线程调用
    __pool = []  # 记录保存的taskId

    def __init__(self, timeKey):
        dataTime = 0
        self.__pool = []
        self.__key = timeKey
        keyTime = int(timeKey[:-1]) * eTimeTs[timeKey[-1]]
        self.__targetTime = datetime.datetime.now() + datetime.timedelta(seconds=keyTime)
        self.__interval = keyTime

        # 大于一天使用定时器
        if keyTime >= 86400:
            # dataTime = str2time(timeKey) #指定时间触发   ,todo:没做
            self.__isRun = False
            # if dataTime != 0:
            # 	# dataTime <= datetime.datetime.now(): 检测时间是否过期
            # 	timeScheduler.add_job(self.intervalUpdate, 'date', id = timeKey, run_date=dataTime)
            # else: #亚洲时间8点1是一天刷新k线数据的时间
            # 	timeScheduler.add_job(self.intervalUpdate, 'cron', hour=8, minute=1, id = timeKey)
            # timeScheduler.add_job(self.intervalUpdate, 'cron', hour=2, minute=58, id = timeKey)

    def pushId(self, taskId):
        if taskId in self.__pool:
            return
        self.__pool.append(taskId)
    # def removeID(self, taskId):
    # 	if taskId in self.__pool:
    # 		index = self.__pool.index(taskId)
    # 		self.__pool.remove(taskId)

    def isRun(self):
        return self.__isRun

    # 普通任务
    def update(self, now):
        if now < self.__targetTime:
            return
        self.__targetTime = datetime.datetime.now(
        ) + datetime.timedelta(seconds=self.__interval)
        # log("~~~触发任务~~~~~",self.__key, datetime.datetime.now())
        # with lock:
        self.notices()
    # 定时器任务
    # def intervalUpdate(self):
    # 	# log("~~~定时器任务~~~~~",datetime.datetime.now(),self.__pool,self)
    # 	with lock:
    # 		self.notices()

    def notices(self):
        if len(self.__pool) == 0:
            return
        evtFire(kEvt_GetTime, self.__key, self.__pool)


class timerMgr:
    "时间管理器"
    __schedules = {}  # 主线程和定时器的时间搓
    __runSchedules = []  # 1天以下的在主线程运行的时间搓

    # 初始化注册时间事件，和时间改动事件
    def __init__(self):
        evtConnect(kEvt_Time, self)
        evtConnect(kEvt_ModifiedTime, self)

    # 固定时间格式 '2023-xx-xx xx:xx' 或 timeTs转换时间
    def addSchedule(self, timeKey, taskId):
        if self.__schedules.get(timeKey) is None:
            objSchedule = schedule(timeKey)
            self.__schedules[timeKey] = objSchedule
            if objSchedule.isRun():  # 是否加入主线程
                self.__runSchedules.append(objSchedule)
        self.__schedules[timeKey].pushId(taskId)

    # 事件接收
    def evtProcess(self, key, *args):
        taskId = args[0]
        tacticsTime = args[1]
        # 添加时间

        def keyTime():
            for time in tacticsTime:  # 添加任务时间搓
                self.addSchedule(time, taskId)
        # todo:修改时间没测试

        def modifiedTime():
            for key, schedule in self.__schedules.items():
                schedule.removeID(taskId)
            keyTime()
        switchFn({kEvt_Time: keyTime, kEvt_ModifiedTime: modifiedTime}, key=key)

    def run(self):
        now = datetime.datetime.now()
        for schedule in self.__runSchedules:
            schedule.update(now)
        # time.sleep(180)

    def show(self):
        print('\n=======定时器列表=====')
        print(self.__schedules)
        # for key in self.__schedules:
        # 	print(">>",key, self.__schedules[key].task())
        # print('==================')
