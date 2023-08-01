from strategy.baseTactics import baseTactics

class vwap(baseTactics):
	'成交量加权平均价格'

	def info(self):
		return "\n\n~~~描述~~~ \nVWAP是一个经过成交量加权的价格平均值，常用于大型基金和机构投资者评估其交易的执行效率。\nVWAP可以用于短期的交易择时，例如当价格高于VWAP时，可能是一个卖出的好时机，反之则可能是买入的好时机。\n\n"

	def launch(self):
		  # self.__timeMgr.addSchedule('1m',1)
        # self._timeMgr.addSchedule('3m',3)
        # self._timeMgr.addSchedule('1m',2)
        # self._timeMgr.addSchedule('1d',4)
        # self._timeMgr.addSchedule('2023-07-3 08:08',5)
		print("vwap初始化")

	def triggers(self):
		return False

	def signal(self):
		pass