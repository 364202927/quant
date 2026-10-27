"""通知模块基类 - 提供共享的 HTTP session 管理"""
import asyncio
import aiohttp
from server.utils.decoratorTool import extInterface
#todo:不要了

class BaseNotify(extInterface):
    """通知服务基类，封装 aiohttp session 管理"""

    def __init__(self):
        super().__init__()
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """确保 session 可用，返回 session 实例"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _close_session(self) -> None:
        """关闭 session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _post_json(self, url: str, payload: dict) -> dict | None:
        """发送 JSON POST 请求，统一错误处理"""
        session = await self._ensure_session()
        try:
            async with session.post(url, json=payload) as resp:
                return await resp.json()
        except aiohttp.ClientError as e:
            print(f"[{self.__class__.__name__}] 网络错误: {e}")
            return None

    async def _get_json(self, url: str, params: dict | None = None) -> dict | None:
        """发送 GET 请求，统一错误处理"""
        session = await self._ensure_session()
        try:
            async with session.get(url, params=params) as resp:
                return await resp.json()
        except aiohttp.ClientError as e:
            print(f"[{self.__class__.__name__}] 网络错误: {e}")
            return None

    async def _idle_loop(self) -> None:
        """空闲循环，用于保持模块运行状态"""
        while True:
            await asyncio.sleep(3600)

    async def run(self) -> None:
        """模块入口，子类需重写"""
        raise NotImplementedError
