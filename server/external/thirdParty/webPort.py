from fastapi import FastAPI
import uvicorn
from server.utils.fileConfig import g_config
from server.utils import evtFire, kEvt_Web, log
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, List
from server.utils.decoratorTool import extInterface

# 约定消息格式
class msgRequest(BaseModel):
    id: int
    args: List[Any] = []

class _webServer(uvicorn.Server):
    """监听成功后打印实际绑定的地址与端口"""
    async def startup(self, sockets=None):
        await super().startup(sockets)
        if not self.started:
            return
        for server in self.servers:
            for sock in server.sockets or []:
                host, port = sock.getsockname()[:2]
                log(f"[web] 已监听 http://{host}:{port}")

class web(extInterface):
    def __init__(self):
        super().__init__()
        self._app = self._create_app()
        self._server = None
    
    def _create_app(self) -> FastAPI:
        app = FastAPI()
        app.add_middleware(CORSMiddleware, 
                    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?", 
                    allow_credentials=True, 
                    allow_methods=["*"], 
                    allow_headers=["*"])
        #消息接收
        @app.post("/api/postMessage")
        async def post_message(msg: msgRequest):
            rt = evtFire(kEvt_Web, msg.id, msg.args)
            return {
                "status": 'success',
                "message": 'post_message 接收成功',
                "received": {
                    "id": msg.id,
                    "args": rt
                }
            }
        
        @app.get("/api/getMessage") #消息id,arg0, arg1: 可选参数
        async def get_Message(id: int, arg0: str = None, arg1: str = None):
            args = []
            if arg0 is not None:
                args.append(arg0)
            if arg1 is not None:
                args.append(arg1)
            
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

    #启动FastAPI
    async def run(self):
        web_config = g_config.external('web')
        config = uvicorn.Config(
            self._app,
            host=web_config.get('host'),
            port=int(web_config.get('port')),
            log_level="info"
        )
        self._server = _webServer(config)
        await self._server.serve()