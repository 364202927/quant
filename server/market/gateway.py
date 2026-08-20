import asyncio
from itertools import count
from server.utils import log, warn, err, evtFireAsync, kEvt_Market
from server.market import eMarketId, kCancel, kPriority_Normal, kPriority_Cancel
from server.market.baseExchange import baseExchange

class gateway:
    "单交易所下单流水线:优先级队列+撤单去重,单消费者协程保证严格顺序提交(ccxt线程安全/杠杆状态约束)"

    def __init__(self, ex: baseExchange, exName: str, preTrade, oms):
        self._ex = ex
        self._exName = exName
        self._preTrade = preTrade
        self._oms = oms
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._seq = count()
        self._closed = False   # 停机时置位,拒收新单

    # 供 marketMgr 的事件处理调用,同步入队(事件总线在事件循环内分发,无跨线程问题)
    def submit(self, data: dict) -> None:
        if self._closed:
            warn(f"[gateway:{self._exName}] 已停止接单,丢弃: {data.get('symbol', '')}")
            return
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

    def close(self) -> None:
        self._closed = True

    async def drain(self, timeout: float = 10.0) -> None:
        "停机时排空在途订单"
        self._closed = True
        try:
            await asyncio.wait_for(self._queue.join(), timeout=timeout)
        except asyncio.TimeoutError:
            warn(f"[gateway:{self._exName}] 排空超时,仍有 {self._queue.qsize()} 笔未提交")

    # 顺序消费本交易所队列: 单消费者保证同一交易所的下单严格串行
    async def run(self) -> None:
        while True:
            _, _, item = await self._queue.get()
            try:
                await self._pipeline(item)
            except Exception as e:
                # 单笔失败不能杀死消费者协程,否则该交易所后续订单全部卡死
                err(f"[gateway:{self._exName}] 流水线异常: {e}")
                self._oms.rollback(item)
            finally:
                self._queue.task_done()

    # 事前风控 → 算价算量 → 记待匹配 → 发单
    async def _pipeline(self, data: dict) -> None:
        reason = self._preTrade.check(data, self._ex)
        if isinstance(reason, str):
            warn(f"[preTrade] 拦截: {reason}")
            return

        reason = await self._oms.prepare(data)
        if reason is not True:
            warn(f"[oms] 拦截: {reason}")
            return

        # 先记录后发单: WS回报可能早于下单REST响应返回,顺序颠倒会导致回报匹配不到记录
        evtFireAsync(kEvt_Market, eMarketId['order'], data)
        try:
            await self._send(data)
        except Exception as e:
            log(f"[gateway:{self._exName}] 下单失败: {e}")
            evtFireAsync(kEvt_Market, eMarketId['orderFailed'], data)
            self._oms.rollback(data)
            self._ex.requestBalanceRefresh()

    async def _send(self, item: dict) -> None:
        if item.get('type') == kCancel:
            await self._ex.order('cancel', item.get('symbol', ''), item.get('orderID', ''), 0)
            self._ex.requestBalanceRefresh()
            return
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
