from server.core.quant import quant
from server.utils import switchFn,evtConnect,kEvt_Web, rtWeb
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
    
    def __init__(self, objQuant:quant):
        self.__instance = objQuant   #quant
        self.__page = 0
        evtConnect(kEvt_Web, self)
    
    def idTransform(self, id, msg):
        def initWeb():
            # 返回数据: user配置 + apiKey配置+start文件
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
            #todo:还有start文件
            return {"user": user, "apiKey": apiKey}
        def initMarketTrends():
            return
        def initStartFile():
            return
        def initBacktesting():
            return self.__instance.getAllTasks()
        def initOrders():
            return
        def saveConfig():#保存设置
            g_config.setConfig(msg[0])
            g_config.saveFile()
            #todo:是否重启服务器
            return
        def startBackTest():#开启回测
            checkId = msg[0].get('id')
            taskName = msg[0].get('selectedTask')
            if checkId == 1:
                return self.callTask(taskName,'startStrategy')
            return {}
        return switchFn({eMsgId['eWebInit']: initWeb,
                        eMsgId['ePage_k']: initMarketTrends,
                        eMsgId['ePage_cta']:initStartFile,
                        eMsgId['ePage_test']:initBacktesting,
                        eMsgId['ePage_order']:initOrders,
                        eMsgId['eSaveFile']:saveConfig,
                        eMsgId['eStartBackTest']:startBackTest},
                        key=id)
    
    # 调用task
    def callTask(self, taskName, fnName):
        rt = self.__instance.callFn(taskName,'startStrategy')
        return rtWeb(rt)

    # 处理web id
    def process(self, id, msg):
        print(f"~~~~~~~~~~[消息处理]~~~~~~~~ 消息ID: {id}, 参数: {msg}")
        rt = self.idTransform(id,msg)
        return rt

    #evt消息
    def evtProcess(self, key, *args):
        id = args[0]
        def setPage():
            self.__page = args[1]
        return switchFn({eMsgId['sPage']: setPage,
                         },key=id)