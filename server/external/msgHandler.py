from server.core.quant import quant
from server.utils import eMsgId,switchFn
from server.utils.fileConfig import g_config

class msgHandler:
    "消息事件处理器"
    
    def __init__(self, objQuant:quant):
        self.__instance = objQuant
    
    def idTransform(self, id, msg):
        def initWeb():
            # 返回数据: user配置 + apiKey配置+start文件
            info = g_config.info()
            external = g_config.external()
            user = {
                "userName": info.get("userName", ""),
                "ccxtRetry": info.get("ccxtRetry", 3),
                "console_e": bool(external.get("console", {}).get("enable", 0)),
                "tg_e": bool(external.get("tg", {}).get("enable", 0))
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
        def startFile():
            return
        def backtesting():
            return
        def orders():
            return
        def saveConfig():#保存设置
            g_config.setConfig(msg[0])
            g_config.saveFile()
            #todo:是否重启服务器
            return
        return switchFn({eMsgId['eWebInit']: initWeb,
                        eMsgId['ePage_k']: initMarketTrends,
                        eMsgId['ePage_cta']:startFile,
                        eMsgId['ePage_test']:backtesting,
                        eMsgId['ePage_order']:orders,
                        eMsgId['eSaveFile']:saveConfig},
                        key=id)

    # 处理接口
    def process(self, id, msg):
        print(f"~~~~~~~~~~[消息处理]~~~~~~~~ 消息ID: {id}, 参数: {msg}")
        rt = self.idTransform(id,msg)
        return rt