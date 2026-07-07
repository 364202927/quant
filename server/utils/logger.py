import sys,os,pprint,json,threading
from server.utils import kLog,kInfo,kError,kWarn
from server.utils.fileConfig import g_config,kLogBufType
from server.utils.common import str2time

_logLock = threading.RLock()

#log显示时间,其他显示 类+调用位置
def _logBase(tag: str, *args) -> None:
    des = '[' + str2time('strNow') + ']' 
    if tag == kLog:
        try:
            frame = sys._getframe(2)
            fileName = os.path.splitext(os.path.basename(frame.f_code.co_filename))[0]
            funcName = frame.f_code.co_name
            lineNo = frame.f_lineno
            des = f"[{fileName}.{funcName}:{lineNo}]"
        except (ValueError, AttributeError):
            des = "[Unknown_Location]"
    message = ''.join(map(str, args))
    fullMessage = des + message
    with _logLock:
        # print("~~~~log~~~~~~",g_config.external('console')['enable'])
        g_config.get(kLogBufType).push(msg=fullMessage, tags=tag)
        if g_config.external('console')['enable'] == False:
            print(fullMessage, flush=True)

def log(*msgs) -> None:
    _logBase(kLog, *msgs)
def info(*msgs) -> None:
    _logBase(kInfo, *msgs)
def warn(*msgs) -> None:
    _logBase(kWarn, *msgs)
def err(*msgs) -> None:
    _logBase(kError, *msgs)
def logFormat(value) -> None:
    _logBase(kLog, "\n", pprint.pformat(value))
def logJson(value) -> None:
    _logBase(kLog, "\n", json.dumps(value, indent=4, ensure_ascii=False))
