"""飞书通知模块"""
import time
import hmac
import hashlib
import base64
from server.external.baseNotify import BaseNotify
from server.utils.fileConfig import g_config


class feishu(BaseNotify):
    """飞书 Webhook 通知服务"""

    def __init__(self):
        super().__init__()
        self._config = g_config.external('feishu')
        self._webhook: str = self._config.get('webhook', '')
        self._secret: str = self._config.get('secret', '')

    def _gen_sign(self, timestamp: int) -> str:
        """生成签名（需配置 secret）"""
        if not self._secret:
            return ''
        string_to_sign = f"{timestamp}\n{self._secret}"
        hmac_code = hmac.new(
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(hmac_code).decode('utf-8')

    def _build_payload(self, payload: dict) -> dict:
        """为 payload 添加签名信息"""
        if self._secret:
            timestamp = int(time.time())
            payload["timestamp"] = str(timestamp)
            payload["sign"] = self._gen_sign(timestamp)
        return payload

    async def send(self, text: str) -> dict | None:
        """发送文本消息"""
        if not self._webhook:
            return None

        payload = self._build_payload({
            "msg_type": "text",
            "content": {"text": text}
        })
        return await self._post_json(self._webhook, payload)

    async def send_card(self, title: str, content: str, color: str = "blue") -> dict | None:
        """发送卡片消息"""
        if not self._webhook:
            return None

        payload = self._build_payload({
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": color
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": content}}
                ]
            }
        })
        return await self._post_json(self._webhook, payload)

    async def run(self) -> None:
        """运行飞书模块"""
        if not self._webhook:
            print("[Feishu] 未配置 webhook，模块已禁用")
            return

        print("[Feishu] 模块已启动")
        try:
            await self._idle_loop()
        finally:
            await self._close_session()
