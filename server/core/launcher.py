import asyncio
from server.core.quant import quant
from server.utils.logger import log
from server.utils.fileConfig import g_config
from server.external.webPort import web
from server.external.cli import cli
from server.external.msgHandler import msgHandler


class launcher:
    "启动器"
    
    def __init__(self):
        self.__modules = []
        self.__quant = None 
        self.__handler = None
        # self.__fastapi_server = None
        # self.__console_monitor = None

        self.init()
    
    def init(self):
        allModule = ['web', 'console'] #todo:添加tg模块
        def create(key: str):
            if key == 'web':
                return web(self._msgTransform)
            return cli(self.__handler)
        # 初始化quant
        self.__quant = quant()
        # self.__quant.set_crash_callback(self._on_crash)
        self.__modules.append(self.__quant)
        self.__handler = msgHandler(self.__quant)
        # 初始化三方模块
        config = g_config.thirdParty()
        for key in allModule:
            if config.get(key).get('enable') == True:
                self.__modules.append(create(key))
        log("Launcher初始化完成",self.__modules)
        
    #消息传递
    def _msgTransform(self, msgID: int, args: list = []):
        if self.__handler:
            return self.__handler.process(msgID, args)
        return None
    
    # 异步驱动
    def run(self):
        asyncio.run(self._async_run())
    async def _async_run(self):
        tasks = []
        for module in self.__modules:
            tasks.append(module.run())
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            log("用户中断，正在退出...")
        # finally:
    
    # 获取模块
    def getModules(self, className: str):
        for module in self.__modules:
            if module.__class__.__name__ == className:
                return module
        return None
    
    # 只执行一个指定的文件，通常用于测试任务
    def onceProject(self, projectName: str):
        self.__quant.loadTask(projectName)
        self.run()
    # 使用start文件启动
    def start(self):
        self.__quant.loadTaskList()
        self.run()