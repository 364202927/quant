from server.core.timerMsg import timerMgr
from server.utils import require, path2File, loadJson, log
import asyncio
from typing import Dict, Any, Optional

kStrategyFile = 'server.strategy.'
kStrategyFile2 = 'server/strategy/'
kStartFile = 'assets.config.start.json'



class quant:
    "量化框架"

    def __init__(self):
        self.__taskMgr = {}
        self.__timeMgr = timerMgr()

        self.__lock = asyncio.Lock()
        # self.__is_running = False
        # self.__stop_event = asyncio.Event()

    def task(self, strategyName):
        return self.__taskMgr.get(strategyName)

    def show(self):
        print('\n=======当前总运行任务=====')
        for key in self.__taskMgr:
            print(">>", key, self.__taskMgr[key])
        print('==================')
    
    async def get_all_tasks_status(self) -> Dict[str, Any]:
        """线程安全获取所有任务状态"""
        async with self.__lock:
            return {
                task_name: {
                    'state': task.state(),
                    'info': task.get('info'),
                    'id': task.get('id'),
                    'className': task.get('className')
                }
                for task_name, task in self.__taskMgr.items()
            }
    
    async def get_task_status(self, task_name: str) -> Optional[Dict[str, Any]]:
        """获取单个任务状态"""
        async with self.__lock:
            task = self.__taskMgr.get(task_name)
            if not task:
                return None
            return {
                'state': task.state(),
                'info': task.get('info'),
                'indicators': task.get('indicators'),
                'id': task.get('id')
            }
    
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
        recoverable_errors = (# 崩溃可恢复类型
            SyntaxError, TypeError, AttributeError, NameError,
            ImportError, ValueError, KeyError, IndexError
        )
        #logic
        try:
            while True:
                await self.__timeMgr.run()
        except recoverable_errors as e:
            log(f"[崩溃]: {type(e).__name__}: {e}")
            # if attempt == max_retries:
            #     raise
            log("[恢复] 尝试重启...")
            await asyncio.sleep(1)
            self.__stop_event.clear()
        except Exception as e:
            log(f"[异常] {type(e).__name__}: {e}")
            raise
    
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
            task = require(kStrategyFile + strategyName)(self.getCta) # todo:需要判断这个文件是不是task用例子
            self.__taskMgr[task.get("className")] = task
            task.active()

    # 加载strategy文件下全部策略
    def loadTask(self, projectName):
        fileList = path2File(kStrategyFile2 + projectName, '.py')
        taskList = [projectName + '.' + file.split('.')[0] for file in fileList]
        self._newTask(taskList)

    # 根据策略文件加载
    def loadTaskList(self, file=kStartFile):
        taskList = []
        config = loadJson(file)
        for fileName in config:
            classTab = config[fileName]
            for i in range(len(classTab)):
                className = classTab[i]
                taskList.append(fileName + '.' + className)
        log("加载文件：", taskList)
        self._newTask(taskList)

    # # 返回共享数据 todo:这里做出修改，应该可获取全部任务（只能可读，不能修改）
    # def getCta(self, ctaName):
    #     allCta = {}
    #     for id in self.__taskMgr:
    #         task = self.__taskMgr[id]
    #         className = task.__class__.__name__
    #         allCta[className] = task.get("store")
    #         if ctaName == className:
    #             return allCta[className]
    #     return allCta