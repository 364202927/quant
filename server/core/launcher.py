import asyncio, signal,traceback
from server.core.engine import engine
from server.utils import g_config,log,kOpenMarket,spawnTask
from server.external import web, cli, msgHandler#, telegram, feishu
from server.market import marketMgr
from server.market.storage.storageCenter import storageCenter
from server.market.storage.storageOrders import storageOrders
from server.market.storage.subscribe import storageSubscribe
from server.utils.watchdog import watchdog

# 模块类型映射表
_MODULE_FACTORY: dict[str, type] = {
    'web': web,
    'console': cli,
    # 'tg': telegram,
    # 'feishu': feishu,
}

kWsReadyTimeout = 30  # 等待交易所WS全部就绪的超时秒数,超时后放行避免单个交易所拖死全部策略启动
kRestartDelay = 1.0   # 模块崩溃后的初始重启延迟(秒),指数退避,上限60s
kShutdownTimeout = 10.0  # 停机时排空在途订单的超时秒数

class launcher:
    """启动器 - 初始化并协调所有模块运行"""

    def __init__(self):
        self.__modules: list = []
        self.__engine: engine = None        #策略任务
        self.__msgHandler:msgHandler = None #消息转换
        self.__marketMgr: marketMgr = None   #交易所(内部持有oms/gateway下单流水线)
        self.__center = None                #账号缓存
        self.__subscribe = None             #交易所 更新/数据缓存
        self.__orders = None                #订单更新/任务订单缓存

        self.__pendingProject: str | None = None  #待加载的测试任务
        self.__pendingStartFile: bool = False     #是否待按start.json加载任务
        self.__stopping = asyncio.Event()
        self.__moduleTasks: list[asyncio.Task] = []
        #
        self._initModules()

    def _initModules(self) -> None:
        self.__msgHandler = msgHandler()
        self.__engine = engine()
        self.__modules.append(self.__engine)
        self.__modules.append(watchdog())

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
        log("Launcher初始化完成")#,self.__modules)

    def run(self) -> None:
        asyncio.run(self._async_run())

    async def _async_run(self) -> None:
        loop = asyncio.get_running_loop()
        self._installSignalHandlers(loop)
        self.__moduleTasks = [spawnTask(self._supervise(m), name=f"module:{m.__class__.__name__}") for m in self.__modules]
        warmupTask = spawnTask(self._loadTasksWhenReady(), name="loadTasksWhenReady")
        try:
            await asyncio.gather(*self.__moduleTasks, warmupTask, return_exceptions=True)
        except (KeyboardInterrupt, asyncio.CancelledError):
            log("用户中断，正在退出...")
        finally:
            warmupTask.cancel()
            await self._shutdown()

    def _installSignalHandlers(self, loop: asyncio.AbstractEventLoop) -> None:
        def _onSignal():
            if self.__stopping.is_set():
                return
            log("[launcher] 收到停机信号,开始优雅退出...")
            self.__stopping.set()
            for t in self.__moduleTasks:
                t.cancel()
        try:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, _onSignal)
        except (NotImplementedError, AttributeError):
            pass  # Windows事件循环不支持add_signal_handler,退化为默认KeyboardInterrupt处理

    # 模块崩溃后指数退避重启,单个模块崩溃不影响其余模块继续运行
    async def _supervise(self, module) -> None:
        delay = kRestartDelay
        while not self.__stopping.is_set():
            try:
                await module.run()
                return  # 模块正常结束(如无交易所配置时的marketMgr.run)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log(f"[{module.__class__.__name__}] 运行异常: {e}")
                traceback.print_exc()
                if self.__stopping.is_set():
                    return
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)

    # 停机序列: 先排空在途订单再关WS,最后强制落盘,顺序不能颠倒
    async def _shutdown(self) -> None:
        self.__stopping.set()
        if self.__subscribe:
            try:
                await self.__subscribe.shutdown()
            except Exception as e:
                log(f"[launcher] K线订阅停机异常: {e}")
        if self.__marketMgr:
            try:
                await self.__marketMgr.shutdown(kShutdownTimeout)
            except Exception as e:
                log(f"[launcher] marketMgr停机异常: {e}")
        for t in self.__moduleTasks:
            if not t.done():
                t.cancel()
        if self.__moduleTasks:
            await asyncio.gather(*self.__moduleTasks, return_exceptions=True)
        if self.__orders:
            self.__orders.flush()
        if self.__center:
            self.__center.flush()
        log("[launcher] 已停机")

    # 等交易所WS全部连接就绪(marketMgr.ready)后再加载任务(触发task.load/init());没有交易所模块时立即加载
    async def _loadTasksWhenReady(self) -> None:
        if self.__marketMgr:
            try:
                await asyncio.wait_for(self.__marketMgr.ready.wait(), timeout=kWsReadyTimeout)
            except asyncio.TimeoutError:
                log(f"[launcher] 等待交易所WS就绪超时({kWsReadyTimeout}s),跳过等待直接加载任务")
        if self.__pendingProject:
            await self.__engine.loadTask(self.__pendingProject)
        elif self.__pendingStartFile:
            await self.__engine.loadTaskList()

    # 通常用于测试任务
    def addProject(self, projectName: str) -> None:
        self.__pendingProject = projectName
    # 根据start.json读取任务
    def start(self) -> None:
        self.__pendingStartFile = True
        self.run()
