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
    "1h": "h",
    "4h": "4H",
    "1D": "D",
    "1W": "W",
    "1M": "M",
}

# 事件
kEvt_Time = 'evtTime'           # 任务时间设定
kEvt_GetTime = 'evtGetTime'     # 任务时间触发
kEvt_Web = 'evtWeb'             #发送和网络通讯相关的参数
kEvt_Market = 'evtMarket'       #交易所相关
kEvt_Engine = 'evtEngine'       #调用task的方法

# eEngineId = {
#     'getRiskConfig': 1,  # args: taskName → returns riskConfig dict
#     'callTask':      2,  # 调用task的方法
# }

#log
kLog,kError,kInfo,kWarn = 'log','err','info','warn'

# 交易所功能是否开启
kOpenMarket = True

# 导出常用工具函数和类
from server.utils.recordBuffer import recordBuffer
from server.utils.fileConfig import g_config
from server.utils.pdData import pdData
from server.utils.science import inRange, binanceTimestamp, time2ID,division
from server.utils.decoratorTool import singleton, extInterface
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
    evtReturn,
    evtFireAsync,
    # evtQuery,
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
    openWeb,
    rtWeb,
    debouncedSaver,
    threadCall,
    spawnTask,
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
    # 'evtQuery',
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
    'rtWeb',
    'debouncedSaver',
    'threadCall',
    'spawnTask',
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
    'extInterface',
    # enumeration
    'eTimeTs',
    'eTaskState',
    'kEvt_GetTime',
    'kEvt_Time',
    'kEvt_Web',
    'kEvt_Market',
    'kEvt_Engine',
    'eEngineId',
    'eSampleTs',
    'eMsgId',
]
