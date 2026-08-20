import asyncio
from server.core.task import task
from server.core.timerMsg import timerMgr
from server.utils import require, path2File, readFile, log, evtConnect,switchFn, kEvt_Engine


# kStrategyFile = 'server.strategy.'
kStrategyFile2 = 'server/strategy/'
kStartFile = 'assets.config.start.json'  #todo:这里修改


class engine:
    "量化引擎"

    def __init__(self):
        self.__taskMgr = {}
        self.__timeMgr = timerMgr()
        evtConnect(kEvt_Engine, self)

    def task(self, strategyName):
        return self.__taskMgr.get(strategyName)

    def show(self):
        print('\n=======当前总运行任务=====')
        for key in self.__taskMgr:
            print(">>", key, self.__taskMgr[key])
        print('==================')

    def getActiveTasks(self):
        taskList = []
        for name, task in self.__taskMgr.items():
            if task.get('active'):
                taskList.append(name)
        return taskList

    def evtProcess(self, key, *args):
        def _callFn(taskName, fnName):
            if taskName == 'main':
                fn = getattr(self, fnName)
                if fn:
                    return fn()
            object = self.__taskMgr.get(taskName)
            if not object:
                return {}
            return object.method(fnName)
        print('~~~~engine:call~~',args)
        if not args:
            return None
        return _callFn(args[0],args[1])

    async def get_task_status(self, task_name: str):
        """获取单个任务状态"""
        # async with self.__lock:
        #     objTask = self.__taskMgr.get(task_name)
        #     if not objTask:
        #         return None
        #     return {
        #         # 'state': task.state(),
        #         'info': objTask.get('info'),
        #         'indicators': objTask.get('indicators'),
        #         'id': objTask.get('id')
        #     }

    # def is_running(self) -> bool:
    #     """检查运行状态"""
    #     return self.__is_running

    # async def run_async(self):
    #     """异步运行主循环，支持外部停止控制"""
    #     # self.__is_running = True
    #     try:
    #         while not self.__stop_event.is_set():
    #             await self.__timeMgr.run()
    #     except Exception as e:
    #         log(f"主循环异常: {e}")
    #         raise
        # finally:
        #     self.__is_running = False

    # async def stop(self):
    #     """停止运行"""
    #     self.__stop_event.set()

    async def run(self):
        # 单次迭代异常隔离: 策略回调抛异常不能让整个定时器静默死亡
        # (否则表现为"定时器停摆,web/cli照常响应,外部完全看不出来")
        while True:
            try:
                await self.__timeMgr.run()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log(f"[engine] 定时器迭代异常: {e}")

    # def run(self, count=True):
    #     """兼容旧版本的同步运行接口"""
    #     async def async_loop():
    #         await self.__timeMgr.run()
    #     if not count:
    #         asyncio.run(async_loop())
    #         exit()
    #     try:
    #         asyncio.run(self.run_async())
    #     except KeyboardInterrupt:
    #         log("用户中断，正在退出...")

    # 创建一个任务
    def _newTask(self, tabStrategy):
        for strategyName in tabStrategy:
            objTask = task()
            if not objTask.bind(strategyName):
                continue
            self.__taskMgr[objTask.get("className")] = objTask

    # 加载strategy文件下全部策略
    def loadTask(self, projectName):
        fileList = path2File(kStrategyFile2 + projectName, '.py')
        taskList = [projectName + '.' + file.split('.')[0] for file in fileList]
        self._newTask(taskList)

    # 根据策略文件加载
    def loadTaskList(self, file=kStartFile):
        taskList = []
        config = readFile(file) #todo:修改
        for fileName in config:
            classTab = config[fileName]
            for i in range(len(classTab)):
                className = classTab[i]
                taskList.append(fileName + '.' + className)
        log("加载文件：", taskList)
        self._newTask(taskList)
