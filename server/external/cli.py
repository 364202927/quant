import asyncio
import aioconsole
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.core.quant import quant


class ConsoleMonitor:
    """Console监控器 - 使用aioconsole实现异步按键监听"""
    
    def __init__(self, quant_instance: 'quant'):
        self._quant = quant_instance
    
    async def run(self):
        """启动控制台监听"""
        print("\n=== Console Monitor Started ===")
        print("输入命令 (h=帮助, q=退出):")
        
        while True:
            try:
                # 异步读取输入
                cmd = await aioconsole.ainput(">>> ")
                await self._handle_command(cmd.strip())
            except EOFError:
                break
            except Exception as e:
                print(f"命令处理错误: {e}")
    
    async def _handle_command(self, cmd: str):
        """处理命令（预留接口）"""
        if cmd == 'q':
            print("退出中...")
            await self._quant.stop()
        elif cmd == 'h':
            self._show_help()
        else:
            # 预留接口
            pass
    
    def _show_help(self):
        """显示帮助信息"""
        print("""
可用命令:
  h     - 显示帮助
  s     - 显示任务状态 [待实现]
  q     - 退出系统
        """)
