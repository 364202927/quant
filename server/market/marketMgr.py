import asyncio
from server.utils import g_config, require, log, evtConnect, evtFire, kEvt_Market, switchFn, spawnTask
from server.market import eMarketId
from server.market.baseExchange import baseExchange
from server.market.gateway import gateway
from server.market.oms import oms
from server.market.risk.preTrade import preTrade
from server.market.risk.circuitBreaker import circuitBreaker
from server.utils.decoratorTool import extInterface

class marketMgr(extInterface):
    "交易所管理"

    def __init__(self):
        super().__init__()
        self.__exchangeMgr: dict = {}
        self.__gateways: dict = {}
        self.__exTasks: list = []
        self.__gwTasks: list = []
        self.__preTrade = preTrade()
        self.__circuitBreaker = circuitBreaker()
        self.ready = asyncio.Event()   # 所有交易所 wsReady 后置位,供 launcher 延迟 task init 使用
        self.initExchange()
        # oms 的本地余额快照来自 initExchange 里 fire 的 balance 事件,构造顺序不能颠倒
        self.__oms = oms(self.get)
        self.__gateways = {name: gateway(ex, name, self.__preTrade, self.__oms)
                           for name, ex in self.__exchangeMgr.items()}
        evtConnect(kEvt_Market, self)

    # ── 交易所初始化 ──
    def initExchange(self):
        def _newExchange(config: dict, name) -> baseExchange:
            exchange: baseExchange = require('server.market.crypto.' + config['exchange'])(config['description'])
            exchange.enroll(config, name)
            exchange.initMarkets()#初始化可交易币种
            return exchange
        #logic
        self.__exchangeMgr = {}
        for name, config in g_config.marketsApi().items():
            if config.get('enable') != True:
                continue
            exchange = _newExchange(config, name)
            self.__exchangeMgr[name] = exchange
            # 初始化账户数据
            bal = exchange.balance()
            evtFire(kEvt_Market, eMarketId['balance'], exchange.get('id'), name, bal)
            # 初始化订单
            open, pos = exchange.findOrder(symbol='',isPos=True,isOpen=True)
            evtFire(kEvt_Market, eMarketId['positions'], exchange.get('id'), name, {'open':open, 'pos':pos}) #账号

            # print(f"激活交易所：{name}, 说明：{config['description']}")
        # if not self.__exchangeMgr:
        #     warn("~~~~~没有交易所激活~~~~~~")

    def get(self, keyName: str = ""):
        if not keyName:
            return self.__exchangeMgr
        return self.__exchangeMgr.get(keyName)

    # ── 事件处理 ──
    def evtProcess(self, key, *args):
        id_ = args[0]
        def _submit():
            data = args[1] if len(args) > 1 else {}
            exName = data.get('exName', '')
            gw = self.__gateways.get(exName)
            if not gw:
                log(f"[marketMgr] 未找到交易所: {exName}")
                return
            gw.submit(data)

        switchFn({eMarketId['submit']: _submit}, key=id_)

    # ── 运行 ──
    async def run(self) -> None:
        if not self.__exchangeMgr:
            self.ready.set()
            return
        self.__exTasks = [spawnTask(ex.run(), name=f"exchange:{name}") for name, ex in self.__exchangeMgr.items()]
        self.__gwTasks = [spawnTask(gw.run(), name=f"gateway:{name}") for name, gw in self.__gateways.items()]
        await asyncio.gather(*[ex.wsReady.wait() for ex in self.__exchangeMgr.values()])
        self.ready.set()
        await asyncio.gather(*self.__exTasks, *self.__gwTasks)

    # ── 停机: 先排空在途订单再关WS,顺序不能颠倒(否则未提交的订单直接丢失) ──
    async def shutdown(self, timeout: float = 10.0) -> None:
        if not self.__exchangeMgr:
            return
        for gw in self.__gateways.values():
            gw.close()
        await asyncio.gather(*(gw.drain(timeout) for gw in self.__gateways.values()), return_exceptions=True)
        for t in self.__gwTasks:
            t.cancel()
        for t in self.__exTasks:
            t.cancel()
        await asyncio.gather(*self.__gwTasks, *self.__exTasks, return_exceptions=True)
        for ex in self.__exchangeMgr.values():
            ex.shutdown()