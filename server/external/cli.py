import asyncio
import aioconsole
from typing import TYPE_CHECKING

# if TYPE_CHECKING:
#     from server.core.quant import quant
from server.external.msgHandler import msgHandler


class cli:
    "Console监控器"
    
    def __init__(self, handler: 'msgHandler' = None):
        self._msgTransform = handler
    
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
            # 通过消息处理器处理命令
            # 将命令作为消息ID，参数为空列表
            if self._message_handler:
                # 简单的命令解析示例
                parts = cmd.split()
                if parts:
                    # 尝试将第一部分转换为消息ID
                    try:
                        msg_id = int(parts[0])
                        args = parts[1:] if len(parts) > 1 else []
                        self._message_handler.handleMessage(msg_id, args)
                    except ValueError:
                        print(f"命令格式错误: '{cmd}' (需要消息ID为整数)")
    
    def _show_help(self):
        """显示帮助信息"""
        print("""
可用命令:
  <message_id> [arg1 arg2 ...]  - 发送消息（message_id为整数）
  h                              - 显示帮助
  s                              - 显示任务状态 [待实现]
  q                              - 退出系统
        """)
