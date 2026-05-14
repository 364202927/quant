# 时间单位转换
eTimeTs = {
    's': 1,
    'm': 60,
    'h': 3600,
    'd': 86400,
}

# pd采样
eSampleTs = {
    "15m": "15min",
    "30m": "30min",
    "1h": "H",
    "4h": "4H",
    "1D": "D",
    "1W": "W",
    "1M": "M",
}

# 事件
kEvt_Time = 'evtTime'  # 任务时间设定
kEvt_GetTime = 'evtGetTime'  # 任务时间触发
kEvt_Web = 'evtWeb'     #发送和网络通讯相关的参数 

#log
kLog,kError,kInfo,kWarn = 'log','err','info','warn'

# 导出常用工具函数和类
from server.utils.recordBuffer import recordBuffer
from server.utils.fileConfig import g_config
from server.utils.pdData import pdData
from server.utils.science import inRange, binanceTimestamp, time2ID,division
from server.utils.decoratorTool import singleton
from server.utils.logger import log,info,warn,err,logJson,logFormat
from server.utils.common import (
    spot,
    swapU,
    swapC,
    futureU,
    futureC,
    require,
    path2File,
    readFile,
    writeFile,
    switch,
    switchFn,
    switchV,
    evtConnect,
    evtFire,
    evtFireAsync,
    split_by,
    slit,
    str2ms,
    reviseTime,
    diff_Pdtime,
    aContainB,
    joinPath,
    getRootName,
    getFileExtension,
    trySwitchFn,
    timeFrame2Float,
    sec2min,
    listFind,
    dictFind,
    utc_now,
    tryCatch,
    str2time,
    openWeb
)

__all__ = [
    # common
    'log',
    'info',
    'warn',
    'err',
    'logFormat',
    'logJson',
    'spot',
    'swapU',
    'swapC',
    'futureU',
    'futureC',
    'require',
    'path2File',
    'readFile',
    'writeFile',
    'switch',
    'switchFn',
    'switchV',
    'evtConnect',
    'evtFire',
    'evtFireAsync',
    'slit',
    'str2ms',
    'reviseTime',
    'diff_Pdtime',
    'aContainB',
    'joinPath',
    'getRootName',
    'getFileExtension',
    'trySwitchFn',
    'timeFrame2Float',
    'sec2min',
    'tryCatch',
    'str2time',
    'listFind',
    'dictFind',
    'recordBuffer',
    'openWeb',
    # fileConfig
    'g_config',
    # pdData
    'pdData',
    # science
    'inRange',
    'binanceTimestamp',
    'time2ID',
    'division',
    # decoratorTool
    'singleton',
    # enumeration
    'eTimeTs',
    'eTaskState',
    'kEvt_GetTime',
    'kEvt_Time',
    'kEvt_Web',
    'eSampleTs',
    'eMsgId',
]
