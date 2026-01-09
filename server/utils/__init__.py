# 时间单位转换
eTimeTs = {
    's': 1,
    'm': 60,
    'h': 3600,
    'd': 86400,
}

# pd采样
eSampleTs = {
    "15m": "15T",
    "30m": "30T",
    "1h": "H",
    "4h": "4H",
    "1D": "D",
    "1W": "W",
    "1M": "M",
}

# 任务状态
eTaskState = {
    'eActive': 0,  # 挂起
    'eWait': 1,  # 等待开单
    'eRun': 2,  # 有单子在进行中
    'eSell': 3,  # 强制结束任务，只能平仓，结束后转换为待激活
}

# 事件
kEvt_Time = 'evtTime'  # 任务时间设定
kEvt_GetTime = 'evtGetTime'  # 任务时间触发

# 导出常用工具函数和类
from server.utils.common import (
    require,
    path2File,
    loadJson,
    switch,
    switchFn,
    switchV,
    evtConnect,
    evtFire,
    evtFireAsync,
    slit,
    str2ms,
    reviseTime,
    diff_Pdtime,
    aContainB,
    joinPath,
    getFileExtension,
    trySwitchFn,
    tryExecution,
)
from server.utils.logger import log, err, warn
from server.utils.fileConfig import g_config
from server.utils.pdData import pdData
from server.utils.science import inRange, binanceTimestamp, time2ID
from server.utils.decoratorTool import singleton

__all__ = [
    # common
    'require',
    'path2File',
    'loadJson',
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
    'tryExecution',
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
]
