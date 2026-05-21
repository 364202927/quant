import abc
from server.utils import warn,switch, evtConnect, evtFire, kEvt_GetTime, kEvt_Time, time2ID, require,eTimeTs,timeFrame2Float
kStrategyFile = 'server.strategy.'

class taskHandle(metaclass=abc.ABCMeta):
    indicators = {}#共享指标
    pause,resume = None,None

    def __init__(self):
        self.tacticsTime = []# 触发时间
    
    def regTime(self, *timeKeys):
        self.tacticsTime = list(timeKeys) if timeKeys else []
    
    def shardIndicators(self,className:str): #根据类名获取指定指标
        return self.indicators.get(className) #todo,这个值改成只能读取不能修改
    def getTacticsTime(self):
        return self.tacticsTime
    def className(self):
        return self.__class__.__name__

#
class task:
    def __init__(self):
        self.info = ''
        self.__id = time2ID()                   # 任务id
        self.__handle = None
        self.isActive = True
        self.isFirst = False
        evtConnect(kEvt_GetTime, self)

    def info(self, strInfo):
        self.info = strInfo

    def get(self, key=''):
        return switch({'tacticsTime': self.__handle.getTacticsTime(),
                       'id': self.__id,
                       'className': self.__handle.className(),
                       'info': self.info,
                       'name': self.__doc__,
                       'active':self.isActive},
                      key=key)

    def bind(self, className: str):
        self.__handle = require(kStrategyFile + className)()
        if not isinstance(self.__handle, taskHandle):
            return False
        self.__handle.pause,self.__handle.resume = self.pause, self.resume
        self.__handle.init()
        if not self.get('tacticsTime'):
            return False
        # 第一次激活向定时器注册任务
        if not self.isFirst:
            self._register()
        return True
    # 是否激活任务
    def pause(self):
        self.isActive = False
    def resume(self):
        self.isActive = True

    # taskHandle fn触发
    def method(self, fnName):
        fn = getattr(self.__handle, fnName, None)
        if callable(fn):
            return fn()

    # 只有第一次激活时注册时间事件
    def _register(self):
        evtFire(kEvt_Time, self.get('id'), self.get('tacticsTime'))
        self.isFirst = True
    
    # 事件处理
    def evtProcess(self, key, *args):
        timeKey = args[0]
        tabId = args[1]
        # 过滤只触发接收的时间戳
        filter = set(self.__handle.getTacticsTime())
        if timeKey not in filter:
            return True
        if not self.isActive:
            if hasattr(self.__handle, "stopProcess"):
                self.__handle.stopProcess()
            return True
        #全时间回调接收，如返回ture不在触发其余时间绑定
        if hasattr(self.__handle, "process"):
            if self.__handle.process(tabId, timeKey):
                return True
        # 绑定时间事件
        time = timeFrame2Float(timeKey)
        timeName = time < 1 and '1sLess' or timeKey
        fnName = 'update_' + timeName
        if hasattr(self.__handle, fnName):
            fnEvt = getattr(self.__handle, fnName)
            fnEvt(tabId, timeKey)
            return True
        warn('当前时间事件未接收:', fnName)
        # self.__handle.evtTime(timeKey)