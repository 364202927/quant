import abc
import asyncio
import inspect
import traceback
from typing import Any
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
    def name(self):
        return self.__class__.__name__

#
class task:
    def __init__(self):
        self.info = ''
        self.__id = time2ID()                   # 任务id
        self.__handle = None
        self.isActive = True
        self.isFirst = False
        self.__eventTask: asyncio.Task | None = None
        evtConnect(kEvt_GetTime, self)

    def info(self, strInfo):
        self.info = strInfo

    def get(self, key=''):
        return switch({'tacticsTime': self.__handle.getTacticsTime(),
                       'id': self.__id,
                       'className': self.__handle.name(),
                       'info': self.info,
                       'name': self.__doc__,
                       'active':self.isActive},
                      key=key)

    async def bind(self, className: str) -> bool:
        self.__handle = require(kStrategyFile + className)()
        if not isinstance(self.__handle, taskHandle):
            return False
        self.__handle.pause,self.__handle.resume = self.pause, self.resume
        loadFn = getattr(self.__handle, 'load', None)
        if not callable(loadFn):
            loadFn = getattr(self.__handle, 'init', None)
        if not callable(loadFn):
            return False
        result = loadFn()
        if inspect.isawaitable(result):
            await result
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
    
    # 事件处理: pydispatch.dispatcher.send 一旦某个receiver抛异常就终止整个分发循环,
    # 同批注册的其余task会被连带跳过一次触发,必须在此拦住策略层异常
    def evtProcess(self, key, *args):
        try:
            return self._evtProcess(*args)
        except Exception as e:
            warn(f"[task:{self.get('className')}] 策略回调异常: {e}")
            traceback.print_exc()
            return True

    def _evtProcess(self, *args):
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
        processFn = getattr(self.__handle, 'process', None)
        time = timeFrame2Float(timeKey)
        timeName = time < 1 and '1sLess' or timeKey
        fnName = 'update_' + timeName
        updateFn = getattr(self.__handle, fnName, None)
        if inspect.iscoroutinefunction(processFn) or inspect.iscoroutinefunction(updateFn):
            if self.__eventTask is not None and not self.__eventTask.done():
                warn(f"[task:{self.get('className')}] 上一次异步回调尚未完成,跳过: {timeKey}")
                return True
            self.__eventTask = asyncio.create_task(
                self._runAsyncEvent(processFn, updateFn, tabId, timeKey))
            return True
        #全时间回调接收，如返回true不再触发其余时间绑定
        if callable(processFn) and processFn(tabId, timeKey):
            return True
        if callable(updateFn):
            updateFn(tabId, timeKey)
            return True
        warn('当前时间事件未接收:', fnName)
        # self.__handle.evtTime(timeKey)

    async def _runAsyncEvent(self, processFn: Any, updateFn: Any,
                             tabId: object, timeKey: str) -> None:
        try:
            if callable(processFn):
                result = processFn(tabId, timeKey)
                if inspect.isawaitable(result):
                    result = await result
                if result:
                    return
            if callable(updateFn):
                result = updateFn(tabId, timeKey)
                if inspect.isawaitable(result):
                    await result
                return
            warn('当前时间事件未接收:', 'update_' + timeKey)
        except asyncio.CancelledError:
            raise
        except Exception as exception:
            warn(f"[task:{self.get('className')}] 异步回调异常: {exception}")
            traceback.print_exc()
