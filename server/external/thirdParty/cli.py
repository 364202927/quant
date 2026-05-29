import asyncio, re, ast, sys, threading
from server.utils.fileConfig import g_config,kLogBufType
from server.utils import kLog,kInfo,kError,kWarn,warn,log,evtFire,kEvt_Web
from server.utils.decoratorTool import extInterface

_IS_WIN = sys.platform == 'win32'
if _IS_WIN:
    import msvcrt
else:
    import tty, termios

kColor= {'red':'\033[31m',
    'green':'\033[32m',
    'yellow':'\033[33m',
    'blue':'\033[34m',
    'magenta':'\033[35m',
    'cyan':'\033[36m',
    'white':'\033[37m'}
kReset = '\033[0m'
kTagColor = {kError: kColor['red'], kWarn: kColor['yellow'],kInfo: kColor['cyan'], kLog: kColor['white']}
kLogFilter = [kLog, kInfo, kError, kWarn] #可显示的打印

class cli(extInterface):
    "Console监控器"

    def __init__(self):
        super().__init__()
    
    def _str2Id(self, src: str) -> dict | None:
        src = src.replace(",", ",").strip()
        parts = [p.strip() for p in src.split(",", 1)]
        # if not parts[0].isdigit():
        #     return None
        id_ = int(parts[0])
        if len(parts) == 1:
            return {"id": id_}
        rest = parts[1].strip()
        if rest.startswith("{"):  # 字典
            return {"id": id_, "args": ast.literal_eval(rest)}
        if "=" in rest:  # key=value 形式
            kv = {k.strip(): int(v.strip())
                  for item in re.split(r"[,\s]+", rest) if item
                  for k, v in [item.split("=", 1)]}
            return {"id": id_, "args": kv}
        # 纯数字列表
        nums = [int(x) for x in re.split(r"[,\s]+", rest) if x]
        return {"id": id_, "args": nums}
    
    async def _printNew(self, input:str):
        def _colorLine(r):
            color = kTagColor.get(r.get('tags', ''), kColor['white'])
            return f"{color}{r.get('data')['msg']}{kReset}\n"
        #打印过滤
        newBuf = g_config.get(kLogBufType).getNew()
        if not newBuf:
            return
        showLog = [buf for buf in newBuf if buf.get('tags') in kLogFilter]
        if not showLog:
            return
        lines = ''.join(_colorLine(r) for r in showLog)
        self._write(f"\r\033[K{lines}{kColor['magenta']}>>> {input}") #输出栏

    def _write(self, text: str):
        sys.stdout.write(text)
        sys.stdout.flush()
    def _initInput(self, loop, queue):
        enqueue = queue.put_nowait
        if _IS_WIN:
            stop = threading.Event()
            def _reader():
                while not stop.is_set():
                    if msvcrt.kbhit():
                        ch = msvcrt.getwch()
                        if ch in ('\x00', '\xe0'):
                            msvcrt.getwch()
                        else:
                            loop.call_soon_threadsafe(enqueue, ch)
                    stop.wait(0.02)
            threading.Thread(target=_reader, daemon=True).start()
            return stop.set
        # Unix: cbreak模式 + event loop reader
        fd = sys.stdin.fileno()
        old_attrs = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        loop.add_reader(fd, lambda: enqueue(sys.stdin.read(1)))
        def _cleanup():
            loop.remove_reader(fd)
            termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
        return _cleanup

    async def run(self):
        print("\n=== Console Monitor Started ===")
        print("输入:(h=帮助, ctrl+c=退出) or (id,value1,...) or (id,x=1,...) or (id,{dict})")

        #输入
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue[str] = asyncio.Queue()
        cleanup = self._initInput(loop, queue)
        buf = ''
        self._write(">>> ")

        try:
            while True:
                try:
                    ch = await asyncio.wait_for(queue.get(), timeout=0.3)
                except asyncio.TimeoutError:
                    await self._printNew(buf)
                    continue

                if ch == '\x03': #ctrl+c
                    exit()
                if ch in ('\n', '\r'): #回车
                    self._write('\n')
                    cmd = buf.strip()
                    buf = ''
                    if cmd:
                        try:
                            await self._handle_command(cmd)
                        except Exception as e:
                            warn("输入异常:",e)
                    self._write(">>> ")
                elif ch in ('\x7f', '\x08'): #del
                    if buf:
                        buf = buf[:-1]
                        self._write('\b \b')
                else: #正常输入
                    buf += ch
                    self._write(ch)

                await self._printNew(buf)
        finally:
            cleanup()
                
    async def _handle_command(self, cmd: str):
        if cmd == 'h':
            log("可用命令:"
                  "\n  <id> [arg1,arg2,...] - 发送消息（id为整数）"
                  "\n  h                   - 显示帮助")
            return
        values = self._str2Id(cmd)
        if values:
            evtFire(kEvt_Web, values['id'], values.get('args'))