import asyncio
from server.utils import evtConnect, kEvt_Market, extInterface, pdData, recordBuffer
from server.market import eMarketId

_FLUSH_INTERVAL = 1.0  # 1秒聚合一次


class storageSubscribe:
    """聚合市场事件：K线→pdData，深度/成交→1s缓冲，订单→recordBuffer"""

    def __init__(self):
        super().__init__()
        self._klineBuffer: dict[tuple, list] = {}   # (exName,symbol,tf) -> [ohlcv,...]
        self._depthLatest: dict[tuple, dict] = {}   # (exName,symbol) -> latest ob
        self._tradesBuffer: dict[tuple, list] = {}  # (exName,symbol) -> [trade,...]
        self.orders = recordBuffer()
        evtConnect(kEvt_Market, self)

    def evtProcess(self, key, *args):
        if len(args) < 2:
            return
        id_, exName = args[0], args[1]
        if id_ == eMarketId['mKline'] and len(args) >= 5:
            k = (exName, args[2], args[3])
            self._klineBuffer.setdefault(k, []).append(args[4])
        elif id_ == eMarketId['mDepth'] and len(args) >= 4:
            self._depthLatest[(exName, args[2])] = args[3]
        elif id_ == eMarketId['mTrades'] and len(args) >= 4:
            buf = self._tradesBuffer.setdefault((exName, args[2]), [])
            buf.extend(args[3] if isinstance(args[3], list) else [args[3]])
        elif id_ == eMarketId['mOrder'] and len(args) >= 3:
            orders = args[2] if isinstance(args[2], list) else [args[2]]
            for order in orders:
                self.orders.push(exName=exName, **order)

    # async def run(self) -> None:
    #     while True:
    #         await asyncio.sleep(_FLUSH_INTERVAL)
    #         self._flush()

    def _flush(self):
        for key, candles in list(self._klineBuffer.items()):
            if not candles:
                continue
            pd_obj = pdData()
            pd_obj.format(candles, style='ohlcv')
            self._klineBuffer[key] = []
        self._depthLatest.clear()
        self._tradesBuffer.clear()
