from include import *
import abc

class baseTactics(metaclass=abc.ABCMeta):
	'策略基类'

	ex = None				#交易所
	symbol = []				#币种，最少5分钟更新一次
	tacticsTime = []		#触发时间

	#todo:资金控制，止损，那些后面做
	def __init__(self, ex):
		self.ex = ex

	def id(self):
		return type(self).__name__
	#修改时间
	def modifiedTime(self, newTime):
		pass
	
	# def freeze(self):
		# pass

	# 策略的描述
	@abc.abstractmethod
	def info(self, strInfo):
		pass

	# 初始化 触发时间, 获取哪些币种的数据
	@abc.abstractmethod
	def launch(self):
		pass

	# 触发信号，获取币种信息后回调
	@abc.abstractmethod
	def triggers(self,kLine):
		return False

	# 交易信号
	@abc.abstractmethod
	def signal(self):
		pass
