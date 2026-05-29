import asyncio
import time
from server.utils import evtConnect, evtFireAsync, kEvt_Market, extInterface, log
from server.market import eMarketId, kPriority_Normal, kPriority_Cancel, kPriority_ForceClose

_MERGE_WINDOW = 0.2   # 200ms 合并窗口
_TWAP_INTERVAL = 0.1  # 100ms TWAP 切片间隔


class oms(extInterface):
    """订单管理：拆分/合并/本地余额校验，路由到 PriorityQueue"""

    def __init__(self):#, queue: asyncio.PriorityQueue, center):
        super().__init__()
        # self._queue = queue
        # self._center = center
        self._localFree: dict[str, dict[str, float]] = {}  # {exName: {coin: amount}}
        self._pendingOrders: dict[str, dict] = {}          # {orderId: order}
        self._mergeWindow: dict[str, list] = {}            # {mkey: [order,...]}
        self._mergeTimer: dict[str, float] = {}            # {mkey: timestamp}
        evtConnect(kEvt_Market, self)

    def evtProcess(self, key, *args):
        if len(args) < 2:
            return
        id_ = args[0]
        if id_ == eMarketId['omsOrder'] and len(args) >= 4:
            asyncio.ensure_future(self._onSignal(args[1], args[2], args[3]))
        elif id_ == eMarketId['sCancel'] and len(args) >= 2:
            asyncio.ensure_future(self._onCancel(args[1]))
        elif id_ == eMarketId['sForceClose'] and len(args) >= 2:
            asyncio.ensure_future(self._onForceClose(args[1]))
        elif id_ == eMarketId['mOrder'] and len(args) >= 3:
            orders = args[2] if isinstance(args[2], list) else [args[2]]
            for order in orders:
                self._reconcile(args[1], order)

    async def _onSignal(self, taskName: str, exName: str, params: dict):
        symbol = params.get('symbol', '')
        side = params.get('side', '')
        amount = float(params.get('amount', 0))
        coin = 'USDT'
        cost = params.get('cost', amount * float(params.get('price', 0) or 0))

        # 本地余额校验
        if cost:
            free = self._localFree.get(exName, {}).get(coin, 0)
            if free < cost:
                center_bal = self._center.balance(exName)
                self._localFree.setdefault(exName, {})[coin] = center_bal.get(coin, 0)
                free = self._localFree[exName][coin]
            if free < cost:
                log(f"[oms] {exName} {symbol} 余额不足 free={free:.2f} < cost={cost:.2f}，拒绝")
                return

        # 合并检测
        mkey = f"{exName}|{symbol}|{side}"
        now = time.monotonic()
        if mkey in self._mergeTimer and now - self._mergeTimer[mkey] < _MERGE_WINDOW:
            self._mergeWindow.setdefault(mkey, []).append(params)
            return
        pending = self._mergeWindow.pop(mkey, [])
        self._mergeTimer[mkey] = now
        if pending:
            amount = sum(float(p.get('amount', 0)) for p in [params] + pending)
            params = {**params, 'amount': amount}

        # 拆分检测
        max_single = float(params.get('maxSingleAmount', 0))
        if max_single and amount > max_single:
            for chunk in self._split(params, max_single):
                self._deduct(exName, coin, float(chunk.get('cost', 0)))
                await self._enqueue(kPriority_Normal, exName, taskName, chunk)
                await asyncio.sleep(_TWAP_INTERVAL)
        else:
            self._deduct(exName, coin, cost)
            await self._enqueue(kPriority_Normal, exName, taskName, params)

    async def _onCancel(self, taskName: str):
        for orderId, order in list(self._pendingOrders.items()):
            if order.get('taskName') == taskName:
                await self._enqueue(kPriority_Cancel, order['exName'], taskName, {**order, 'state': 'cancel'})

    async def _onForceClose(self, taskName: str):
        await self._enqueue(kPriority_ForceClose, '', taskName, {'state': 'forceClose'})

    def _reconcile(self, exName: str, order: dict):
        orderId = order.get('orderId', '')
        status = order.get('status', '')
        if status in ('cancel', 'rejected'):
            orig = self._pendingOrders.pop(orderId, None)
            if orig:
                self._refund(exName, 'USDT', float(orig.get('cost', 0)))
        elif status == 'closed':
            orig = self._pendingOrders.pop(orderId, None)
            if orig:
                real_cost = float(order.get('cumQuote', 0))
                diff = float(orig.get('cost', 0)) - real_cost
                if diff > 0:
                    self._refund(exName, 'USDT', diff)

    def _split(self, params: dict, max_amount: float) -> list[dict]:
        remaining = float(params.get('amount', 0))
        chunks = []
        while remaining > 0:
            chunk_amt = min(remaining, max_amount)
            chunks.append({**params, 'amount': chunk_amt})
            remaining -= chunk_amt
        return chunks

    def _deduct(self, exName: str, coin: str, amount: float):
        bal = self._localFree.setdefault(exName, {})
        bal[coin] = max(0.0, bal.get(coin, 0.0) - amount)

    def _refund(self, exName: str, coin: str, amount: float):
        bal = self._localFree.setdefault(exName, {})
        bal[coin] = bal.get(coin, 0.0) + amount

    async def _enqueue(self, priority: int, exName: str, taskName: str, params: dict):
        # await self._queue.put((priority, {'exName': exName, 'taskName': taskName, 'params': params}))
        pass

    async def run(self) -> None:
        while True:
            await asyncio.sleep(3600)
