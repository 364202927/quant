from include import *
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from data.user.shareDate import g_share

# todo销毁任务
# todo:主线程和副线程之间的调度，可能有问题
# todo:默认是5分钟取一次k线并保存，低于1分钟的k线，需要在交易所重新获取

# 定时器
job_defaults = { 'max_instances': 20}#最大支持定时器 个数
timeScheduler = BackgroundScheduler(timezone= 'Asia/Hong_Kong', job_defaults=job_defaults)
timeScheduler.start()

# def clearTime(timeKey):
# 	timeScheduler.remove_job(timeKey)

class schedule:
	"触发的时间搓"
	__interval = 0
	__targetTime = 0
	__isRun = True
	__objPool = {}		#对象池

	def __init__(self, timeKey):
		self.__targetTime = datetime.datetime.now() + datetime.timedelta(seconds=int(timeTs[timeKey]))
		dataTime = 0
		self.__objPool = {}
		# 判断传入的是固定时间或者普通时间
		if timeTs.get(timeKey):
			self.__interval = int(timeTs[timeKey])
		else:
			dataTime = str2time(timeKey) #todo:~~~~ 可能报错
			self.__interval = int(timeTs['d'])
			# if dataTime == None or dataTime <= self.__targetTime:
			if dataTime == None or dataTime <= datetime.datetime.now():
				err(timeKey,"创建时间出错")
			
		# 日期或1天以上使用定时器
		if self.__interval >= int(timeTs['d']):
			self.__isRun = False
			if dataTime != 0:
				timeScheduler.add_job(self.intervalUpdate, 'date', id = timeKey, run_date=dataTime, args=[self])
			else: #亚洲时间8点1是一天刷新k线数据的时间
				timeScheduler.add_job(self.intervalUpdate, 'cron', hour=8, minute=1, id = timeKey, args=[self])

	def regObj(self, objTactics):
		tacticsId = objTactics.id()
		if self.__objPool.get(tacticsId):
			err(tacticsId,":多次注册相同任务",)
			return
		self.__objPool[tacticsId] = objTactics

	def unRegObj(self, objTactics):
		tacticsId = objTactics.id()
		if self.__objPool[tacticsId]:
			del self.__objPool[tacticsId]

	def isRun(self):
		return self.__isRun
	def task(self):
		return self.__objPool

	# 触发绑定的任务
	def notices(self):
		#如果是5分钟时间段，先触发k线更新
		if self.__interval >= int(timeTs['5m']):
			g_share.update()
		#更新其余k线
		for key, obj in self.__objPool.items():
			data = g_share.getKline(obj.ex.name(),obj.symbol)
			obj.triggers()

	# 普通任务
	def update(self, now):
		if now < self.__targetTime:
			return
		self.__targetTime = datetime.datetime.now() + datetime.timedelta(seconds=self.__interval)
		log("~~~触发任务~~~~~",self.__interval, datetime.datetime.now())
		self.notices()

	# 定时器任务
	def intervalUpdate(self):
		log("~~~定时器任务~~~~~",datetime.datetime.now(),self.__objPool)
		self.notices()


# 1.处理任务时间改变
# 2.不删除任务，只处理时间改变

class timerMgr:
	"时间管理器"
	__schedules = {}  	#全部时间调度
	__runSchedules = []	#普通运行时间搓

	def __init__(self):
		evtConnect(kEvt_Time, self)
		evtConnect(kEvt_ModifiedTime, self)

	#固定时间格式 '2023-xx-xx xx:xx' 或 timeTs转换时间
	def addSchedule(self, timeKey, objTactics = None):
		if self.__schedules.get(timeKey) == None:
			objSchedule = schedule(timeKey)
			self.__schedules[timeKey] = objSchedule
			if objSchedule.isRun(): #是否加入主线程
				self.__runSchedules.append(objSchedule)
		if objTactics:
			self.__schedules[timeKey].regObj(objTactics)

	# 修改时间(策略对象,新时间)
	def modifiedTime(self, objTactics, newTime):
		pass
	
	#事件接收
	def evtProcess(self, key, *args):
		objTactics = args[0]
		tacticsTime = objTactics.tacticsTime
		# 添加时间
		def keyTime():
			if len(self.__schedules) == 0 and len(tacticsTime) > 0: #第一次初始化添加5分钟刷新
				self.addSchedule("5m")
			for time in tacticsTime:
				self.addSchedule(time, objTactics)

		# 修改时间
		def modifiedTime():
			pass

		tab = {
			"evtTime": keyTime,
			"evtModifiedTime": modifiedTime,
		}
		if tab.get(key):
			tab[key]()

	def run(self):
		now = datetime.datetime.now()
		for schedule in self.__runSchedules:
			schedule.update(now)

	def show(self):
		print('\n=======定时器列表=====')
		for key in self.__schedules:
			print(">>",key, self.__schedules[key].task())
		print('==================')