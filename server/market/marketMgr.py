import asyncio
from server.utils import g_config, require, err, log, warn, tryCatch, logFormat, evtConnect, kEvt_Market
from server.market.baseExchange import baseExchange
from server.market.risk.preTrade import preTrade
from server.market.risk.circuitBreaker import circuitBreaker

from server.utils.decoratorTool import extInterface


class marketMgr(extInterface):
    "交易所管理"

    def __init__(self):
        super().__init__()
        # self.__user: dict = {'all': {}}
        self._preTrade = preTrade()
        self._circuitBreaker = circuitBreaker()
        self.updateExchange()
        evtConnect(kEvt_Market, self)
    #更新全交易所数据
    def updateExchange(self):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.__exchangeMgr: dict = {}
        # self.__user: dict = {'all': {}}
        for name, config in g_config.marketsApi().items():
            if config.get('enable') == 1:
                self._newExchange(name, config)
        if not self.__exchangeMgr:
            warn("~~~~~没有交易所激活~~~~~~")

    def _newExchange(self, exName: str, config: dict) -> None:
        exchange = require('server.market.crypto.' + config['exchange'])(config['description'])
        exchange.enroll(config)
        self.__exchangeMgr[exName] = exchange
        exchange.markets()
        acc = tryCatch(lambda: exchange.account())
        if acc:
            self._center.seed(exName, acc)
        print(f"激活交易所：{exName}, 说明：{config['description']}")

    #todo:不需要了,改在center记录
    def get(self, keyName: str = "") -> baseExchange:
        if not keyName:
            return self.__exchangeMgr
        return self.__exchangeMgr[keyName]
    def userAccount(self, exName: str = "", isUpdate: bool = False) -> dict:
        if not isUpdate:
            return self.__user['all'] if not exName else self.__user.get(exName, {})
        targets = [exName] if exName else list(self.__exchangeMgr)
        for name in targets:
            ex = self.__exchangeMgr.get(name)
            self.__user[name] = ex.account()
        summary = {}
        for name in self.__exchangeMgr:
            acc = self.__user.get(name)
            for coin, val in acc['total'].items():
                summary[coin] = summary.get(coin, 0) + float(val)
        self.__user['all'] = summary
        log("账户数据已更新, 交易所数量:", len(targets))
        return summary

    # def subModules(self) -> list:
    #     return [self._center, self._subscribe, self._oms, self._preTrade, self._circuitBreaker]

    def evtProcess(self, key, *args):
        pass

    async def run(self) -> None:
        if not self.__exchangeMgr:
            return
        ex_tasks = [ex.run() for ex in self.__exchangeMgr.values()]
        await asyncio.gather(self._dispatchOrders(), *ex_tasks)

    async def _dispatchOrders(self) -> None:
        while True:
            priority, item = await self._queue.get()
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
