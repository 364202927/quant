import asyncio
from server.utils import g_config, require, err, log, warn, tryCatch, logFormat, evtConnect, evtFire, kEvt_Market
from server.market import eMarketId
from server.market.baseExchange import baseExchange
from server.market.risk.preTrade import preTrade
from server.market.risk.circuitBreaker import circuitBreaker
from server.utils.decoratorTool import extInterface


class marketMgr(extInterface):
    "交易所管理"

    def __init__(self):
        super().__init__()
        # self.__user: dict = {'all': {}}
        self.__exchangeMgr: dict = {}
        self.__queue: asyncio.PriorityQueue = None
        self.__preTrade = preTrade()
        self.__circuitBreaker = circuitBreaker()
        self.initExchange()
        evtConnect(kEvt_Market, self)
    #更新全交易所数据
    def initExchange(self):
        def _newExchange(config: dict,name) -> baseExchange:
            exchange:baseExchange = require('server.market.crypto.' + config['exchange'])(config['description'])
            exchange.enroll(config, name)
            # coin = exchange.initMarkets()#初始化可交易币种
            return exchange
        # logic
        self.__exchangeMgr = {}
        self.__queue = asyncio.PriorityQueue()
        for name, config in g_config.marketsApi().items():
            if config.get('enable') == 1:
                exchange = _newExchange(config, name)
                self.__exchangeMgr[name] = exchange
                # 初始化账户数据
                # bal = exchange.balance()
                # evtFire(kEvt_Market, eMarketId['balance'], exchange.get('id'), name, bal) 
                # 初始化订单
                # open,pos = exchange.findOrder(symbol='',isPos=True,isOpen=True)
                # evtFire(kEvt_Market, eMarketId['positions'], exchange.get('id'), name, {'open':open, 'pos':pos}) #账号
                # print(f"激活交易所：{name}, 说明：{config['description']}")
        # if not self.__exchangeMgr:
        #     warn("~~~~~没有交易所激活~~~~~~")

    def get(self, keyName: str = ""):
        if not keyName:
            return self.__exchangeMgr
        return self.__exchangeMgr[keyName]
    # def userAccount(self, exName: str = "", isUpdate: bool = False) -> dict:
    #     if not isUpdate:
    #         return self.__user['all'] if not exName else self.__user.get(exName, {})
    #     targets = [exName] if exName else list(self.__exchangeMgr)
    #     for name in targets:
    #         ex = self.__exchangeMgr.get(name)
    #         self.__user[name] = ex.account()
    #     summary = {}
    #     for name in self.__exchangeMgr:
    #         acc = self.__user.get(name)
    #         for coin, val in acc['total'].items():
    #             summary[coin] = summary.get(coin, 0) + float(val)
    #     self.__user['all'] = summary
    #     log("账户数据已更新, 交易所数量:", len(targets))
    #     return summary

    # def subModules(self) -> list:
    #     return [self._center, self._subscribe, self._oms, self._preTrade, self._circuitBreaker]

    def evtProcess(self, key, *args):
        pass

    async def run(self) -> None:
        if not self.__exchangeMgr:
            return
        ex_tasks = [ex.run() for ex in self.__exchangeMgr.values()]
        await asyncio.gather(self._gateway(), *ex_tasks)
    # 下单
    async def _gateway(self) -> None:
        while True:
            priority, item = await self.__queue.get()
            exName = item.get('exName', '')
            params = item.get('params', {})
            ex = self.__exchangeMgr.get(exName)
            if not ex:
                log(f"[marketMgr] 未找到交易所: {exName}")
                continue
            try:
                order_params = {
                    'state':      params.get('state', params.get('side', '')),
                    'symbol':     params.get('symbol', ''),
                    'totelPrice': params.get('totelPrice', params.get('cost', 0)),
                    'amount':     float(params.get('amount', 0)),
                    'price':      params.get('price'),
                    'isMarket':   params.get('isMarket', False),
                    'inForce':    params.get('inForce', 'GTC'),
                    'posSide':    params.get('posSide'),
                    'lv':         int(params.get('lv', 1)),
                }
                ex.order(**order_params)
            except Exception as e:
                log(f"[marketMgr] 下单失败 {exName}: {e}")
