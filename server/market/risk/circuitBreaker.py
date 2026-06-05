import asyncio
from server.utils import evtConnect, evtFireAsync, kEvt_Market, kEvt_Engine, extInterface, log
from server.market import eMarketId

_NORMAL_INTERVAL = 60.0   # 正常检测间隔 1m
_VOLATILE_INTERVAL = 1.0  # 行情波动大时 1s
_LOSS_LIMIT = 5            # 连续亏损笔数阈值


class circuitBreaker:
    """断路器：监听余额骤降和策略连续亏损，触发撤单+平仓+暂停"""

    def __init__(self):
        # super().__init__()
        self._lossCount: dict[str, int] = {}   # {taskName: count}
        self._tripped: set[str] = set()        # 已触发断路的策略
        self._interval = _NORMAL_INTERVAL
        evtConnect(kEvt_Market, self)

    def evtProcess(self, key, *args):
        # if len(args) < 2:
        #     return
        # id_ = args[0]
        # if id_ == eMarketId['iHolding'] and len(args) >= 5:
        #     self._onHolding(args[1], args[2], args[3], args[4])
        # elif id_ == eMarketId['mOrder'] and len(args) >= 3:
        #     orders = args[2] if isinstance(args[2], list) else [args[2]]
        #     for order in orders:
        #         self._onOrder(order)
        pass

    def _onHolding(self, exName: str, kind: str, current: dict, prev: dict):
        if kind != 'balance':
            return
        drop_pct = 0.20  # 余额骤降 20% 触发，可从 riskConfig 扩展
        for coin, prev_amt in prev.items():
            if prev_amt <= 0:
                continue
            curr_amt = current.get(coin, 0)
            if prev_amt and (prev_amt - curr_amt) / prev_amt >= drop_pct:
                log(f"[circuitBreaker] {exName} {coin} 余额骤降，触发断路")
                self._interval = _VOLATILE_INTERVAL
                asyncio.ensure_future(self._trip(exName))
                return

    def _onOrder(self, order: dict):
        taskName = order.get('taskName', '')
        if not taskName or taskName in self._tripped:
            return
        config = self._riskConfig(taskName)
        loss_limit = config.get('consecutiveLossLimit', _LOSS_LIMIT)
        pnl = float(order.get('realizedPnl', 0))
        self._lossCount[taskName] = self._lossCount.get(taskName, 0) + 1 if pnl < 0 else 0
        if self._lossCount.get(taskName, 0) >= loss_limit:
            log(f"[circuitBreaker] {taskName} 连续亏损 {loss_limit} 笔，触发断路")
            asyncio.ensure_future(self._trip(taskName))

    async def _trip(self, name: str):
        if name in self._tripped:
            return
        self._tripped.add(name)
        await evtFireAsync(kEvt_Market, eMarketId['sCancel'], name)
        await evtFireAsync(kEvt_Market, eMarketId['sForceClose'], name)
        await evtFireAsync(kEvt_Market, eMarketId['iCircuitTrip'], name)

    def _riskConfig(self, name: str) -> dict:
        # return evtQuery(kEvt_Engine, eEngineId['getRiskConfig'], name) or {}
        pass

    # async def run(self) -> None:
    #     while True:
    #         await asyncio.sleep(self._interval)
    #         if self._interval == _VOLATILE_INTERVAL:
    #             self._interval = _NORMAL_INTERVAL
