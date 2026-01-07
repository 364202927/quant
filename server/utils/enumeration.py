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
kEvt_ModifiedTime = 'evtModifiedTime'  # 任务修改时间
kEvt_GetTime = 'evtGetTime'  # 任务时间触发
kEvt_Signal = 'evtSignal'  # 指标信号触发
