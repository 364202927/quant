import asyncio
from server.core.quant import quant
from server.utils.logger import log
from server.utils.fileConfig import g_config
from server.external.webPort import FastAPIServer
from server.external.cli import ConsoleMonitor


class launcher:
    "启动器"
    
    def __init__(self):
        self.__modules = []
        self.__quant = None
        self.__fastapi_server = None
        self.__console_monitor = None

        self.init()
    
    def init(self):
        def create(key: str):
            if key == 'web':
                return FastAPIServer(self.__quant, g_config)
            return ConsoleMonitor(self.__quant)
        # 初始化quant
        self.__quant = quant()
        self.__quant.set_crash_callback(self._on_crash)
        self.__modules.append(self.__quant)
        # 初始化第三方模块
        config = g_config.thirdParty()
        module = ['web', 'console'] #todo:添加tg模块
        for key in module:
            if config.get(key).get('enable') == True:
                self.__modules.append(create(key))
        log("Launcher初始化完成",self.__modules)
    
    async def _on_crash(self, error: Exception, crash_count: int):
        """崩溃回调 - 发送通知"""
        msg = f"量化系统崩溃！\n错误: {error}\n崩溃次数: {crash_count}"
        log(f"[崩溃通知] {msg}")
        # TODO: 调用邮件/TG通知
    
    # 异步驱动
    async def _async_run(self):
        tasks = []
        for module in self.__modules:
            tasks.append(module.run())
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            log("用户中断，正在退出...")
        # finally:
        #     await self._shutdown()
    def run(self):
        asyncio.run(self._async_run())

    # 调试用，优先使用start
    def testTask(self,projectName: str):
        self.__quant.loadTask(projectName)

    # 使用start文件启动
    def start(self):
        self.__quant.loadList()
        self.run()
    
    # async def _shutdown(self):
    #     """清理资源"""
    #     log("正在关闭所有服务...")
    #     if self.__quant:
    #         await self.__quant.stop()