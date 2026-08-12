import asyncio
from server.core.engine import engine
from server.utils import g_config,log,kOpenMarket
from server.external import web, cli, msgHandler#, telegram, feishu
from server.market import marketMgr
from server.market.oms import oms
from server.market.storage.center import storageCenter
from server.market.storage.orders import storageOrders
from server.market.storage.subscribe import storageSubscribe
import traceback

# 模块类型映射表
_MODULE_FACTORY: dict[str, type] = {
    'web': web,
    'console': cli,
    # 'tg': telegram,
    # 'feishu': feishu,
}

kWsReadyTimeout = 30  # 等待交易所WS全部就绪的超时秒数,超时后放行避免单个交易所拖死全部策略启动

class launcher:
    """启动器 - 初始化并协调所有模块运行"""

    def __init__(self):
        self.__modules: list = []
        self.__engine: engine = None        #策略任务
        self.__msgHandler:msgHandler = None #消息转换
        self.__marketMgr: marketMgr = None   #交易所
        self.__oms:oms  =None               #订单管理
        self.__center = None                #账号缓存
        self.__subscribe = None             #交易所 更新/数据缓存
        self.__orders = None                #订单更新/任务订单缓存
        self.__pendingProject: str | None = None  #待加载的测试任务
        self.__pendingStartFile: bool = False     #是否待按start.json加载任务
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
            self.__center = storageCenter()
            self.__orders = storageOrders()
            self.__marketMgr = marketMgr()
            self.__modules.append(self.__marketMgr)
            #k线数据订阅每5分钟触发数据更新
            self.__subscribe = storageSubscribe()
            self.__subscribe.setMarket(self.__marketMgr.get())
            # evtFire(kEvt_Time, 'subscribe', ['5m'])
            self.__oms = oms(self.__marketMgr.get)
        log("Launcher初始化完成")#,self.__modules)

    def run(self) -> None:
        asyncio.run(self._async_run())
    async def _async_run(self) -> None:
        async def _guard(module):
            try:
                await module.run()
            except Exception as e:
                log(f"[{module.__class__.__name__}] 运行异常: {e}")
                traceback.print_exc()
        try:
            await asyncio.gather(*[_guard(m) for m in self.__modules], self._loadTasksWhenReady())
        except (KeyboardInterrupt, asyncio.CancelledError):
            log("用户中断，正在退出...")

    # 等交易所WS全部连接就绪(marketMgr.ready)后再加载任务(触发task.init());没有交易所模块时立即加载
    async def _loadTasksWhenReady(self) -> None:
        if self.__marketMgr:
            try:
                await asyncio.wait_for(self.__marketMgr.ready.wait(), timeout=kWsReadyTimeout)
            except asyncio.TimeoutError:
                log(f"[launcher] 等待交易所WS就绪超时({kWsReadyTimeout}s),跳过等待直接加载任务")
        if self.__pendingProject:
            self.__engine.loadTask(self.__pendingProject)
        elif self.__pendingStartFile:
            self.__engine.loadTaskList()

    # 通常用于测试任务
    def addProject(self, projectName: str) -> None:
        self.__pendingProject = projectName
    # 根据start.json读取任务
    def start(self) -> None:
        self.__pendingStartFile = True
        self.run()
