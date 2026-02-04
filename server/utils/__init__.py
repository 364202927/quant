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

eMsgId = {
    #get数据，获取信息
    'eWebInit':1000, #web初始化
    'ePage_k':1001,  #行情 
    'ePage_cta':1002,
    'ePage_test':1003,
    'ePage_order':1004,
    #save数据，设置信息
    'eSaveFile':10000, #保存
}
# 事件
kEvt_Time = 'evtTime'  # 任务时间设定
kEvt_GetTime = 'evtGetTime'  # 任务时间触发

# 导出常用工具函数和类
from server.utils.logger import log, err, warn
from server.utils.fileConfig import g_config
from server.utils.pdData import pdData
from server.utils.science import inRange, binanceTimestamp, time2ID
from server.utils.decoratorTool import singleton
from server.utils.common import (
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
    getFileExtension,
    trySwitchFn,
    timeFrame2Float,
    sec2min,
    listFind,
    dictFind,
    utc_now,
    tryCatch
)

__all__ = [
    # common
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
    'getFileExtension',
    'trySwitchFn',
    'timeFrame2Float',
    'sec2min',
    'tryCatch',
    'listFind',
    'dictFind',
    # logger
    'log',
    'err',
    'warn',
    # fileConfig
    'g_config',
    # pdData
    'pdData',
    # science
    'inRange',
    'binanceTimestamp',
    'time2ID',
    # decoratorTool
    'singleton',
    # enumeration
    'eTimeTs',
    'eTaskState',
    'kEvt_GetTime',
    'kEvt_Time',
    'eSampleTs',
    'eMsgId',
]
