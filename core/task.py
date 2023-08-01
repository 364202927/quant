from include import *
from data.user.shareDate import g_share
# 当前任务用的所有策略信息全部共享
# 夸任务需要另外做保存

#把交易所从task传入strtegy
#记录任务状态，是否开了单子
# 1.处理任务时间改变
# 2.不删除任务，只处理时间改变


# 任务一旦启动，检测订单状态，如开始后中途分强制取消（强制结算单子）和预备取消（当前单子都完成后不在开单），
# todo:dataCenter:数据中心
# todo:任务状态没做

class task:
	'任务'

	__name = ''
	__info = ''
	__state = None		#任务当前状态
	__ex = None			#交易所
	__strategys = []	#绑定的策略

	def __init__(self, name, ex):
		self.__name = name
		self.__ex = ex
		self.__strategys = []
		# self.__jobID = newJobID()

	def info(self, strInfo):
		self.__info = strInfo

	def addStrategy(self, strTactics):
		strategy = require('strategy.' + strTactics)(self.__ex)			
		self.regStrategy(strategy)

	def delStrategy(self, strTactics):
		pass
	def clear(self, strTactics):
		pass
	def modified(self, exName = None, strTactics = None, timeTab = None):
		pass

	# def setState(self):
	# 	pass
	# def pause(self):
	# 	pass
	# def resume(self):
	# 	pass

	# 注册策略
	def regStrategy(self, strategy):
		# print(strategy.ex, strategy.symbol, strategy.tacticsTime)
		strategy.launch()
		evtFire(kEvt_Time, strategy)
		g_share.regSymbols(self.__ex.name(), strategy.symbol)
		# todo续测试 二次修改时间

		self.__strategys.append(strategy)