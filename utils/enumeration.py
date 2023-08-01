# 时间转换, 币种跟交易所限制最少是5分钟取一次数据
timeTs = {
    '~':'0',
    '1s': "1",
    '1m': '60',
    '3m': '180',
    '5m': '300',
    '15m': '900',
    '30m': '1800',
    '1h': '3600',
    '2h': '7200',
    '4h': '14400',
    '6h': '21600',
    '12h': '43200',
    'd': '86400',
    'w': '604800',
    'M': '2678400',
    '3M': '8035200',
    '6M': '16070400',
    '1y': '31536000'
}

sampleTs = {
    "15m":"15T",
    "30m":"30T",
    "1h":"H",
    "4h":"4H",
    "d":"D",
    "w":"W",
    "m":"M",
}

# 任务枚举
kTaskState = {
    'eWait':0,  #等待
    'eRun':1,   #正常运行
    'eLock':2,  #有单子在进行中
    'eSell':3,  #强制单向操作，只能卖，卖出后转为等待
}

#任务状态
kTaskState = {
	'eActive':0, #待激活
	'eRun':1,	#正常运行
	'eStop':2,	 #停止
	'eWait':3,    #等待
}

#事件
kEvt_Time = 'evtTime'                   #绑定时间触发
kEvt_ModifiedTime = 'evtModifiedTime'      #修改绑定时间