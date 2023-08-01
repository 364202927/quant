from core.quant import *

def main():
	objQuant = quant()
	
	# todo:记录上次的打开的策略


	# objQuant.addJob("测试任务",'bybit',["timings.boll","timings.vwap"])
	# objQuant.show()


	objQuant.start('bybit_child',["timings.boll"])

if __name__ == "__main__":
	# try:
		main()
		# x = 1/0
	# except Exception as e:
		# print("程序崩溃，错误信息：", str(e))
		# todo:检测发送通知


