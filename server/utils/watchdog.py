import asyncio
from server.utils.decoratorTool import extInterface
from server.utils.fileConfig import g_config
from server.utils.logger import warn

kCheckInterval = 0.1    # 采样间隔(秒)
kDefaultThreshold = 0.5 # 告警阈值(秒): 单次迭代实际耗时超过 采样间隔+阈值 就告警

class watchdog(extInterface):
    "事件循环阻塞探测器: 定期测量loop被占用的滞后时间,超阈值告警"

    def __init__(self):
        super().__init__()
        config = g_config.info().get('watchdog', {})
        self._enable = config.get('enable', True)
        self._threshold = config.get('threshold', kDefaultThreshold)

    async def run(self) -> None:
        if not self._enable:
            return
        loop = asyncio.get_running_loop()
        while True:
            t0 = loop.time()
            await asyncio.sleep(kCheckInterval)
            lag = loop.time() - t0 - kCheckInterval
            if lag > self._threshold:
                warn(f"[watchdog] 事件循环阻塞 {lag:.2f}s (阈值 {self._threshold}s),"
                     f"排查同步IO/CPU密集调用")
