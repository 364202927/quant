import asyncio
from server.utils import g_config, require, err, log, warn, tryCatch, logFormat, evtConnect, evtFire, kEvt_Market, switchFn
from server.market import eMarketId, kPriority_Normal, kPriority_Cancel, kPriority_ForceClose, kCancel
from server.market.baseExchange import baseExchange
from server.market.risk.preTrade import preTrade
from server.market.risk.circuitBreaker import circuitBreaker
from server.utils.decoratorTool import extInterface

class marketMgr(extInterface):
    "交易所管理"

    def __init__(self):
        super().__init__()
        self.__exchangeMgr: dict = {}
        self.__queue: asyncio.PriorityQueue = None
        self.__preTrade = preTrade(self.get)
        self.__circuitBreaker = circuitBreaker()
        self.initExchange()
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
        self.__queue = asyncio.PriorityQueue()
        for name, config in g_config.marketsApi().items():
            if config.get('enable') != True:
                continue
            exchange = _newExchange(config, name)
            self.__exchangeMgr[name] = exchange
            # 初始化账户数据
            bal = exchange.balance()
            evtFire(kEvt_Market, eMarketId['balance'], exchange.get('id'), name, bal) 
            # # 初始化订单
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
        def _order():
            data = args[1] if len(args) > 1 else {}
            orderType = data.get('type', '')
            exName = data.get('exName', '')
            symbol = data.get('symbol', '')

            # 优先级: 撤单=1, 普通=5 (强平=0 预留)
            if orderType == kCancel:
                priority = kPriority_Cancel
                # 撤单去重：检查队列中是否已有相同 symbol + exName 的撤单
                dup = False
                for p, item in list(self.__queue._queue):
                    if (item.get('type') == kCancel and
                        item.get('symbol') == symbol and
                        item.get('exName') == exName):
                        dup = True
                        break
                if dup:
                    log(f"[marketMgr] 撤单重复，跳过: {symbol} @ {exName}")
                    return
            else:
                priority = kPriority_Normal

            self.__queue.put_nowait((priority, data))

        switchFn({eMarketId['order']: _order}, key=id_)

    # ── 运行 ──
    async def run(self) -> None:
        if not self.__exchangeMgr:
            return
        ex_tasks = [ex.run() for ex in self.__exchangeMgr.values()]
        await asyncio.gather(self._gateway(), *ex_tasks)

    # ── 下单网关 ──
    async def _gateway(self) -> None:
        while True:
            priority, item = await self.__queue.get()
            exName = item.get('exName', '')
            orderType = item.get('type', '')
            ex:baseExchange = self.__exchangeMgr.get(exName)
            if not ex:
                log(f"[marketMgr] 未找到交易所: {exName}")
                continue
            try:
                # print("~order~~~", item)
                if orderType == kCancel:
                    # 撤单: (state, symbol, orderID, 0)
                    ex.order('cancel', item.get('symbol', ''),
                                item.get('orderID', ''), 0)
                else:
                    # 普通下单
                    ex.order(
                        typeState=item.get('dir', ''),
                        symbol=item.get('symbol', ''),
                        totelPrice=item.get('totelPrice', 0),
                        amount=item.get('amount'),
                        price=item.get('price'),
                        isMarket=item.get('isMarket', False),
                        inForce=item.get('inForce', 'GTC'),
                        posSide=item.get('posSide'),
                        lv=item.get('lv', 1),
                    )
            except Exception as e:
                log(f"[marketMgr] 下单失败 {exName}: {e}")
