from utils.fileConfig import g_config
from utils.decoratorTool import *

@singleton
class console:
	__input = None

	def __init__(self):
		self.__input = g_config.thirdParty()['console']['enable'] == 1
		# print("~~~console~~~~~~", self.__input)

	def run(self):
		if self.__input != True:
			return
		
		print("请输入指令:")
		user_input = input('> ')
		self.process_input(user_input)

	def process_input(self, useInput):
		if useInput == '1':
			print('Hello, World!')
		elif useInput == 'q':
			exit()
    	# else:
        	# self.run(self)

		# def a():
		# 	pass
		# def b():
		# 	pass
		# # logic
		# funTab = {
		# 	'a':a,
		# 	'b':b,
		# }
		# if funTab.get(self.name()):
		# 	return funTab[self.name()]()

g_console = console()
