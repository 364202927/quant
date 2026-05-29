"""Telegram 通知模块"""
import asyncio
from server.external.baseNotify import BaseNotify
from server.utils.fileConfig import g_config
from server.utils import  kEvt_Web


class telegram(BaseNotify):
    """Telegram Bot 通知服务"""

    def __init__(self):
        super().__init__()
        self._config = g_config.external('tg')
        self._bot_token: str = self._config.get('token', '')
        self._chat_id: str = self._config.get('chatId', '')
        self._base_url = f"https://api.telegram.org/bot{self._bot_token}"
        self._polling: bool = self._config.get('polling', False)
        self._offset = 0

    async def send(self, text: str, chat_id: str | None = None) -> dict | None:
        """发送消息到 Telegram"""
        if not self._bot_token:
            return None

        target_chat = chat_id or self._chat_id
        if not target_chat:
            return None

        payload = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": "HTML"
        }
        return await self._post_json(f"{self._base_url}/sendMessage", payload)

    async def _get_updates(self) -> list:
        """获取 Telegram 更新消息"""
        params = {"offset": self._offset, "timeout": 30}
        data = await self._get_json(f"{self._base_url}/getUpdates", params)
        if data and data.get("ok"):
            return data.get("result", [])
        return []

    async def _handle_update(self, update: dict) -> None:
        """处理收到的消息，解析命令格式: /cmd arg1 arg2"""
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")

        if not text or not chat_id or not text.startswith("/"):
            return

        parts = text[1:].split()
        cmd = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        # if cmd.isdigit():
            # result = evtQuery(kEvt_Web, int(cmd), args)
            # if result:
            #     await self.send(str(result), str(chat_id))

    async def _poll_loop(self) -> None:
        """轮询消息循环"""
        print("[Telegram] 开始轮询消息...")
        while True:
            updates = await self._get_updates()
            for update in updates:
                self._offset = update["update_id"] + 1
                await self._handle_update(update)
            await asyncio.sleep(1)

    async def run(self) -> None:
        """运行 Telegram 模块"""
        if not self._bot_token:
            print("[Telegram] 未配置 bot_token，模块已禁用")
            return

        print(f"[Telegram] 模块已启动 (polling={self._polling})")
        try:
            if self._polling:
                await self._poll_loop()
            else:
                await self._idle_loop()
        finally:
            await self._close_session()
