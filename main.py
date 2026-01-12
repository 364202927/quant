from server.core.launcher import launcher
from server.utils.common import publicIp


def main():
    print("当前ip地址:", publicIp())
    # 启动
    launch = launcher()
    # 测试任务
    launch.testTask(projectName='testStrategy')
    launch.run()

    # *优先使用start文件启动
    # launch.start()


if __name__ == "__main__":
    main()