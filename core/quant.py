from include import *
from market.markets import g_marketMgr
from deploy.console import g_console
from core.timerMsg import timerMgr
from core.task import task

#todo:会将所有策略用到的币种讯息收集起，每5分钟获取一次


class quant:
    "主流程"
    
    __timeMgr = None
    __taskMgr = None

    def __init__(self):
        self.__initMarker()
        self.__initThirdParty()
        self.__taskMgr = {}
        self.__timeMgr = timerMgr()

    def __initMarker(self):
        for key in g_config.markets():
            market_config = g_config.markets()[key]
            if market_config['enable'] == 1:
                g_marketMgr.newExchange(key,
                                        market_config["exchange"],
                                        market_config["apiKey"],
                                        market_config["secret"],
                                        market_config["description"])

    def __initThirdParty(self):
        # log("~~~~__ThirdParty~~~~",g_config.thirdParty())
        pass

    def __run(self):
        g_console.run()
        self.__timeMgr.run()

    def start(self, strEx = "", testStrategyTab = []):
        if len(testStrategyTab) > 0:
            self.addJob("策略调试", strEx, testStrategyTab)
        while True:
            self.__run()

    def show(self):
        print('\n=======当前总运行任务=====')
        for key in self.__taskMgr:
            print(">>", key, self.__taskMgr[key])
        print('==================')


    def addJob(self, name, strEx, strategyTab = None):
        if self.__taskMgr.get(name):
            err("任务重名")
            return
        # todo 检测交易所是否存在
        newTask = task(name, g_marketMgr.getExchange(strEx))
        # 返回task
        self.__taskMgr[name] = newTask
        if strategyTab == None:
            return newTask
        # 创建策略
        for strStrategy in strategyTab:
            newTask.addStrategy(strStrategy)
        
        #todo:可去掉打印任务
        self.__timeMgr.show()


    def clearJob(self):
        pass
    def getTask(self, name):
        pass