import aioconsole, re,ast
from server.utils import split_by

class cli:
    "Console监控器"
    
    def __init__(self, fnHandler):
        self._msgTransform = fnHandler
    
    def _parseStr(self, src: str):
        src = src.replace("，", ",").strip()
        parts = [p.strip() for p in src.split(",", 1)]
        id_ = int(parts[0])
        if len(parts) == 1:
            return {"id": id_}

        rest = parts[1].strip()
        # 字典（以 { 开头）
        if rest.startswith("{"):
            return {"id": id_,"args": ast.literal_eval(rest)}
        # key=value 形式
        if "=" in rest:
            kv = {}
            items = re.split(r"[,\s]+", rest)
            for item in items:
                if not item:
                    continue
                k, v = item.split("=", 1)
                kv[k.strip()] = int(v.strip())
            return {"id": id_,"args": kv}
        # 纯数字列表（逗号或空格分割）
        nums = [int(x) for x in re.split(r"[,\s]+", rest) if x]
        return {"id": id_,"args": nums}

    async def run(self):
        print("\n=== Console Monitor Started ===")
        print("输入:(h=帮助, ctrl+c=退出) or (id,value1,...) or (id,x=1,...) or (id,{dict})")
        while True:
            # try:
                cmd = await aioconsole.ainput(">>> ")
                await self._handle_command(cmd.strip())
            # except Exception as e:
            #     print(f"输入错误: {e}")
    #消息处理
    async def _handle_command(self, cmd: str):
        if cmd == 'h':
            print("""
        可用命令:
        <message_id> [arg1 arg2 ...]  - 发送消息（message_id为整数）
        h                              - 显示帮助""")
        else:
           # 转换格式
            values = self._parseStr(cmd)
            self._msgTransform(values.get('id'), values.get('args'))
            # print(f"输入",cmd)