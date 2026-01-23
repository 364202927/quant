import aioconsole
from server.utils import split_by

class cli:
    "Console监控器"
    
    def __init__(self, fnHandler):
        self._msgTransform = fnHandler
    
    async def run(self):
        print("\n=== Console Monitor Started ===")
        print("输入:(h=帮助, ctrl+c=退出) or (id,value1,...)")
        while True:
            try:
                cmd = await aioconsole.ainput(">>> ")
                await self._handle_command(cmd.strip())
            except Exception as e:
                print(f"命令处理错误: {e}")
    #消息处理
    async def _handle_command(self, cmd: str):
        if cmd == 'h':
            print("""
        可用命令:
        <message_id> [arg1 arg2 ...]  - 发送消息（message_id为整数）
        h                              - 显示帮助""")
        else:
           # 转换格式：id,argr = []
            args = split_by(cmd, ',') 
            id = args[0]
            args = args[1:] if len(args) > 1 else []
            rt = self._msgTransform(id, args)
            # print(f"输入",cmd)
        
