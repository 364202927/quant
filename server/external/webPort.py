from fastapi import FastAPI
import uvicorn
from server.utils.fileConfig import g_config
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, List
from server.external.interface import ExternalInterface

# 约定消息格式
class msgRequest(BaseModel):
    id: int
    args: List[Any] = []

class web(ExternalInterface):
    def __init__(self, fnHandler):
        super().__init__(fnHandler)
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
        async def post_message(msg: msgRequest):
            # rt = self._msgTransform.process(msg.id, msg.args)
            rt = self._msgTransform(msg.id, msg.args)
            print("~~~~~~back msg~~~~~~~",rt)
            return {
                "status": 'success',
                "message": 'post_message 接收成功',
                "received": {
                    "id": msg.id,
                    "args": rt
                }
            }
        
        @app.get("/api/getMessage")
        async def get_Message(id: int, arg0: str = None, arg1: str = None):
            """
            接收 GET 消息
            id: 消息 ID
            arg0, arg1: 可选参数
            """
            args = []
            if arg0 is not None:
                args.append(arg0)
            if arg1 is not None:
                args.append(arg1)
            
            if self._message_handler:
                self._message_handler.handleMessage(id, args)
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
        web_config = g_config.external('web')
        config = uvicorn.Config(
            self._app,
            host=web_config.get('host'),
            port=int(web_config.get('port')),
            log_level="info"
        )
        # print('~~~~~',web_config.get('host'),web_config.get('port'))
        self._server = uvicorn.Server(config)
        await self._server.serve()