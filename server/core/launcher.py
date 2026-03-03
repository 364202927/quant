import asyncio
from server.utils.common import log
from server.core.quant import quant
from server.utils.fileConfig import g_config
from server.external import web, cli, msgHandler, telegram, feishu
from server.market import g_marketMgr

# 模块类型映射表
_MODULE_FACTORY: dict[str, type] = {
    'web': web,
    'console': cli,
    # 'tg': telegram,
    # 'feishu': feishu,
}

class launcher:
    """启动器 - 初始化并协调所有模块运行"""

    def __init__(self):
        self.__modules: list = []
        self.__quant: quant | None = None
        self.__idTransform: msgHandler | None = None
        self._initModules()

    def _initModules(self) -> None:
        self.__quant = quant()
        self.__modules.append(self.__quant)
        self.__idTransform = msgHandler(self.__quant)

        # 根据配置启用三方模块
        config = g_config.external()
        for key, cls in _MODULE_FACTORY.items():
            module_config = config.get(key, {})
            if module_config.get('enable'):
                self.__modules.append(cls(self._msgTransform))

        log("Launcher初始化完成", self.__modules)

        # 交易所更新
        if g_config.marketsApi():
            g_marketMgr.init()
            g_marketMgr.userAccount(isUpdate=True)
    # 消息引导
    def _msgTransform(self, msgID: int, args: list | None = None):
        if self.__idTransform:
            return self.__idTransform.process(msgID, args or [])
        return None
    # 通常用于测试任务
    def addProject(self, projectName: str) -> None:
        self.__quant.loadTask(projectName)
    def run(self) -> None:
        asyncio.run(self._async_run())
    async def _async_run(self) -> None:
        tasks = [module.run() for module in self.__modules]
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            log("用户中断，正在退出...")
    
    # def getModules(self, className: str):
    #     for module in self.__modules:
    #         if module.__class__.__name__ == className:
    #             return module
    #     return None
    
    # 根据任务链表读取
    def start(self) -> None:
        self.__quant.loadTaskList()
        self.run()