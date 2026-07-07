from server.core.launcher import launcher
# from server.utils.common import publicIp
# import webbrowser

def main():
    # print("当前ip地址:", publicIp())
    # 启动
    launch = launcher()
    # # 测试任务
    launch.addProject(projectName='testStrategy')
    launch.run()
    # *优先使用start文件启动
    # launch.start()

    # safari = webbrowser.get('safari')
    # safari.open('http://localhost:5173/')

if __name__ == "__main__":
    main()