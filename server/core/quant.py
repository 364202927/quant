from server.core.timerMsg import timerMgr
from server.utils.common import require, path2File, loadJson
from server.utils.logger import log
# from server.market.markets import g_marketMgr
# from deploy.console import g_console

kStrategyFile = 'server.strategy.'
kStrategyFile2 = 'server/strategy/'
kStartFile = 'assets.config.start.json'


class quant:
    "主流程"
    
    __timeMgr = None
    __taskMgr = None

    def __init__(self):
        self.__taskMgr = {}
        self.__timeMgr = timerMgr()

        # todo创建交易所,初始化用户数据，加载历史数据
        # g_marketMgr.init()
        # g_userCenter.init()
        # self.__initThirdParty()

    # def __initMarker(self):
    #     for name in g_config.markets():
    #         market_config = g_config.markets()[name]
    #         if market_config['enable'] == 1:
    #             g_marketMgr.newExchange(name, market_config)

    def __initThirdParty(self):
        # log("~~~~__ThirdParty~~~~",g_config.thirdParty())
        pass

    def task(self, strategyName):
        return self.__taskMgr.get(strategyName)

    def show(self):
        print('\n=======当前总运行任务=====')
        for key in self.__taskMgr:
            print(">>", key, self.__taskMgr[key])
        print('==================')

    # 运行一次或一直运行
    def run(self, count=True):
        def loop():
            # g_console.run()
            self.__timeMgr.run()

        if not count:
            loop()
            exit()
        while True:
            loop()

    # 创建任务
    def newTask(self, tabStrategy):
        for strategyName in tabStrategy:
            task = require(kStrategyFile + strategyName)(self.getCta)
            self.__taskMgr[task.get("className")] = task
            task.active()

    # 加载strategy文件下全部策略
    def loadTask(self, projectName):
        fileList = path2File(kStrategyFile2 + projectName, '.py')
        taskList = [
            projectName + '.' + file.split('.')[0] for file in fileList
        ]
        self.newTask(taskList)

    # 根据策略文件加载
    def loadTaskList(self, file=kStartFile):
        taskList = []
        config = loadJson(file)
        for fileName in config:
            classTab = config[fileName]
            for i in range(len(classTab)):
                className = classTab[i]
                taskList.append(fileName + '.' + className)
        log("加载文件：", taskList)
        self.newTask(taskList)

    # 根据文件快速启动
    def start(self):
        self.loadList()
        self.run()

    # 返回共享数据
    def getCta(self, ctaName):
        allCta = {}
        for id in self.__taskMgr:
            task = self.__taskMgr[id]
            className = task.__class__.__name__
            allCta[className] = task.get("store")
            if ctaName == className:
                return allCta[className]
        return allCta
