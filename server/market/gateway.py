import asyncio
from itertools import count
from server.utils import log
from server.market import kCancel, kPriority_Normal, kPriority_Cancel
from server.market.baseExchange import baseExchange

class gateway:
    "单交易所下单网关:优先级队列+撤单去重,交易所内部严格顺序提交(ccxt线程安全/杠杆状态约束)"

    def __init__(self, ex: baseExchange, exName: str):
        self._ex = ex
        self._exName = exName
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._seq = count()

    # 供 marketMgr 的事件处理调用,同步入队
    def submit(self, data: dict) -> None:
        orderType = data.get('type', '')
        if orderType == kCancel:
            if self._hasDupCancel(data.get('symbol', '')):
                log(f"[gateway:{self._exName}] 撤单重复，跳过: {data.get('symbol', '')}")
                return
            priority = kPriority_Cancel
        else:
            priority = kPriority_Normal
        self._queue.put_nowait((priority, next(self._seq), data))

    def _hasDupCancel(self, symbol: str) -> bool:
        for _, _, item in list(self._queue._queue):
            if item.get('type') == kCancel and item.get('symbol') == symbol:
                return True
        return False

    # 顺序消费本交易所队列
    async def run(self) -> None:
        while True:
            _, _, item = await self._queue.get()
            await self._submitOne(item)

    async def _submitOne(self, item: dict) -> None:
        orderType = item.get('type', '')
        try:
            if orderType == kCancel:
                await self._ex.order('cancel', item.get('symbol', ''), item.get('orderID', ''), 0)
                self._ex.requestBalanceRefresh()
            else:
                result = await self._ex.order(
                    typeState=item.get('orderDir', item.get('dir', '')),
                    symbol=item.get('symbol', ''),
                    totelPrice=item.get('totelPrice', 0),
                    amount=item.get('amount'),
                    price=item.get('price'),
                    isMarket=item.get('isMarket', False),
                    inForce=item.get('inForce', 'GTC'),
                    posSide=item.get('posSide'),
                    lv=item.get('lv', 1),
                    clientOrderId=item.get('clientOrderId'))
                if result is None:
                    self._ex.requestBalanceRefresh()
        except Exception as e:
            log(f"[gateway:{self._exName}] 下单失败: {e}")
            self._ex.requestBalanceRefresh()
