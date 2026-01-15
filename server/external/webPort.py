from fastapi import FastAPI
import uvicorn,webbrowser,sys
from server.utils.fileConfig import g_config
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, List

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.core.quant import quant

# 定义请求数据模型
class MessageRequest(BaseModel):
    id: int
    args: List[Any] = []


class web:
    """FastAPI服务器框架"""
    
    def __init__(self, quant_instance: 'quant'):
        self._quant = quant_instance
        self._app = self._create_app()
        self._server = None
    
    def _create_app(self) -> FastAPI:
        app = FastAPI()
        app.add_middleware(CORSMiddleware, 
                    allow_origins=["http://localhost:5173"], 
                    allow_credentials=True, 
                    allow_methods=["*"], 
                    allow_headers=["*"])
        #消息接收
        @app.post("/api/postMessage")
        def post_message(msg: MessageRequest):
            """
            接收 POST 消息
            msg.id: 消息 ID
            msg.args: 参数列表
            """
            print(f"~111~~post_message~~~~~")
            print(f"  消息ID: {msg.id}")
            print(f"  参数列表: {msg.args}")
            return {
                "status": 'success',
                "message": 'post_message 接收成功',
                "received": {
                    "id": msg.id,
                    "args": msg.args
                }
            }
        
        @app.get("/api/getMessage")
        async def get_Message(id: int, arg0: str = None, arg1: str = None):
            """
            接收 GET 消息
            id: 消息 ID
            arg0, arg1: 可选参数
            """
            print(f"~222~~get_Message~~~~~")
            print(f"  消息ID: {id}")
            print(f"  参数: arg0={arg0}, arg1={arg1}")
            return {
                "status": 'success',
                "message": 'get_Message 接收成功',
                "received": {
                    "id": id,
                    "arg0": arg0,
                    "arg1": arg1
                }
            }
        
        return app
    
    async def run(self):
        """启动FastAPI服务器"""
        web_config = g_config.thirdParty().get('web')
        config = uvicorn.Config(
            self._app,
            host=web_config.get('host'),
            port=web_config.get('port'),
            log_level="info"
        )
        # print('~~~~~',web_config.get('host'),web_config.get('port'))
        self._server = uvicorn.Server(config)
        await self._server.serve()

    def openWeb(self):
        if sys.platform.startswith("darwin"):#macos
            safari = webbrowser.get('safari')
            safari.open('http://localhost:5173/')
            return
        webbrowser.open('http://localhost:5173/')