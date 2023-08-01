from strategy.baseTactics import *

class boll(baseTactics):
	'布林线策略'

	def info(self):
		return "\n\n~~~描述~~~ \n收盘价由下向上穿过上轨的时候，做多；然后由上向下穿过中轨的时候，平仓。\n收盘价由上向下穿过下轨的时候，做空；然后由下向上穿过中轨的时候，平仓。\n\n"

	def launch(self):
		# self.symbol = ['btc/usdt','eth/usdt']
		# self.tacticsTime = ['1m']
		
		# log("sss",self.ex)
		# _pf = self.ex.getHistoryCandles('spot_BTCUSDT',['2023-05-01 00:00:00', 'now'],fileName = "BTCUSDT.pkl")
		# _pf.show()
		
		# pdObj = pdData()
		# pdObj.readFile('BTCUSDT.csv')
		# pdObj.resample("15m")
		# pdObj.show()
		
		# _pf = self.ex.getKline('spot_BTCUSDT',['2023-07-01 00:00:00', 'now'],limit = 1)
		# print(_pf)

		# self.ex.oblcv('btc/usdt')
		pass


	def triggers(self, kLine):
		print("~~~~boll.triggers~ba~")
		return False

	def signal(self):
		pass