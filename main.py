from server.core import quant
from server.utils.common import publicIp


def main():
    print("当前ip地址:", publicIp())
    print("启动策略")
    objQuant = quant()
    # objQuant.newTask(tabStrategy=['testStrategy.test'])
    objQuant.loadTask(projectName='testStrategy')
    # objQuant.loadTaskList()
    objQuant.run()
    # objQuant.start()


if __name__ == "__main__":
    # try:
    main()
    # except Exception as e:
    # 	print("\n程序崩溃,错误信息:", str(e))
    # 	print("当前ip地址:",publicIp())
