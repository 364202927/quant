import asyncio
from server.core.engine import engine
from server.utils import switchFn,evtConnect, rtWeb,evtFire,kEvt_Web,kEvt_Engine,log
from server.utils.fileConfig import g_config

eMsgId = {
    #set数据,内部通知
    'sPage':10,

    #get数据，获取信息
    'eWebInit':1000, #web初始化
    'ePage_k':1001,  #行情page 
    'ePage_cta':1002, #策略管理page
    'ePage_test':1003, #回测page
    'ePage_order':1004, #订单管理
    #save数据，设置信息
    'eSaveFile':10000, #保存
    'eStartBackTest':11000,#开启回测
}

class msgHandler:
    "消息事件处理器"
    
    def __init__(self):
        self.__page = 0
        evtConnect(kEvt_Web, self)
    
    def idTransform(self, id, msg):
        def initWeb():
            info = g_config.info()
            external = g_config.external() 
            user = {
                "userName": info.get("userName", ""),
                "ccxtRetry": info.get("ccxtRetry", 3),
                "console_e": bool(external.get("console", {}).get("enable", 0)),
                "tg_e": bool(external.get("tg", {}).get("enable", 0)),
                "feishu_e": bool(external.get("feishu", {}).get("enable", 0)),
                'page': self.__page
            }
            apiKey = {
                "market": g_config.marketsApi(),
                "newsletter": g_config.newsletterApi(),
                "ai": g_config.aiApi()
            }
            # print("~~~~~~~initWeb~~~~~~~~",user,apiKey)
            # 返回数据: user配置 + apiKey配置+start文件
            return {"user": user, "apiKey": apiKey} #todo:还有start文件
        def initMarketTrends():
            return
        def initStartFile():
            return
        def initBacktesting():
            return self.callTask('main','getActiveTasks')
        def initOrders():
            return
        def saveConfig():#保存设置
            g_config.setConfig(msg[0])
            g_config.saveFile()
            #todo:是否重启服务器
            return
        def startBackTest():#开启回测: 立即返回"已启动",实际回测在下一轮事件循环调度,不卡住本次web请求
            checkId = msg[0][0].get('id')
            taskName = msg[0][0].get('selectedTask')
            if checkId == 1:
                asyncio.create_task(self._runBackTest(taskName))
                return {'status': 'started'}
            return {}
        return switchFn({eMsgId['eWebInit']: initWeb,
                        eMsgId['ePage_k']: initMarketTrends,
                        eMsgId['ePage_cta']:initStartFile,
                        eMsgId['ePage_test']:initBacktesting,
                        eMsgId['ePage_order']:initOrders,
                        eMsgId['eSaveFile']:saveConfig,
                        eMsgId['eStartBackTest']:startBackTest},
                        key=id)
    
    async def _runBackTest(self, taskName: str) -> None:
        try:
            self.callTask(taskName, 'startStrategy')
        except Exception as e:
            log(f"[msgHandler] 回测启动失败: {e}")

    # 调用engine功能
    def callTask(self, taskName, fnName):
        rt = evtFire(kEvt_Engine, taskName, fnName)
        if taskName =='main':
            return rt
        return rtWeb(rt)

    # 处理web id
    def process(self, id, msg):
        print(f"~~~~~~~~~~[消息处理]~~~~~~~~ 消息ID: {id}, 参数: {msg}")
        rt = self.idTransform(id,msg)
        return rt

    #evt消息
    def evtProcess(self, key, *args):
        id = args[0]
        msg = list(args[1:]) if len(args) > 1 else []
        def setPage():
            self.__page = msg[0] if msg else 0
        if id == eMsgId['sPage']:
            setPage()
            return None
        return self.idTransform(id, msg)