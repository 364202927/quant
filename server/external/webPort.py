from fastapi import FastAPI
import uvicorn
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.core.quant import quant


class FastAPIServer:
    """FastAPI服务器框架"""
    
    def __init__(self, quant_instance: 'quant', config):
        self._quant = quant_instance
        self._config = config
        self._app = self._create_app()
        self._server = None
    
    def _create_app(self) -> FastAPI:
        """创建FastAPI应用"""
        app = FastAPI(title="Quant System API", version="1.0.0")
        
        @app.get("/api/health")
        async def health_check():
            """健康检查"""
            return {
                "status": "running" if self._quant.is_running() else "stopped"
            }
        
        @app.get("/api/tasks")
        async def get_tasks():
            """获取所有任务状态（预留接口）"""
            pass
        
        return app
    
    async def run(self):
        """启动FastAPI服务器"""
        web_config = self._config.thirdParty().get('web', {})
        host = web_config.get('host', '0.0.0.0')
        port = web_config.get('port', 8000)
        
        config = uvicorn.Config(
            self._app,
            host=host,
            port=port,
            log_level="info"
        )
        self._server = uvicorn.Server(config)
        await self._server.serve()
