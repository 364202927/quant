import asyncio
from server.core.engine import engine
from server.utils import g_config,log,kOpenMarket
from server.external import web, cli, msgHandler, telegram, feishu
from server.market import marketMgr
from server.market.oms import oms
from server.market.storage.center import storageCenter
from server.market.storage.subscribe import storageSubscribe

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
        self.__engine: engine = None        #策略任务
        self.__msgHandler:msgHandler = None #消息转换
        self.__marketMgr: marketMgr = None   #交易所
        self.__oms:oms  =None               #订单管理
        self.__center:storageCenter = None  #账号缓存
        self.__subscribe:storageSubscribe=None #订单/交易所最新数据
        #
        self._initModules()

    def _initModules(self) -> None:
        self.__msgHandler = msgHandler() 
        self.__engine = engine()
        self.__modules.append(self.__engine)

        # 根据配置启用三方模块
        config = g_config.external()
        for key, cls in _MODULE_FACTORY.items():
            module_config = config.get(key, {})
            if module_config.get('enable'):
                self.__modules.append(cls())
        # 交易所模块
        if kOpenMarket and g_config.marketsApi():
            self.__marketMgr = marketMgr()
            self.__modules.append(self.__marketMgr)
        log("Launcher初始化完成")

    # 通常用于测试任务
    def addProject(self, projectName: str) -> None:
        self.__engine.loadTask(projectName)
    def run(self) -> None:
        asyncio.run(self._async_run())
    async def _async_run(self) -> None:
        async def _guard(module):
            try:
                await module.run()
            except Exception as e:
                log(f"[{module.__class__.__name__}] 运行异常: {e}")
        try:
            await asyncio.gather(*[_guard(m) for m in self.__modules])
        except (KeyboardInterrupt, asyncio.CancelledError):
            log("用户中断，正在退出...")

    # 根据start.json读取任务
    def start(self) -> None:
        self.__engine.loadTaskList()
        self.run()