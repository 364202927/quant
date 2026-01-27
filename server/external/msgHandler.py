from server.core.quant import quant
from server.utils import eMsgId,switchFn
from server.utils.fileConfig import g_config

class msgHandler:
    "消息事件处理器"
    
    def __init__(self, objQuant:quant):
        self.__instance = objQuant
    
    def idTransform(self, id, msg):
        def initWeb():
            #返回数据 1.设置面板.username  2.market数据 3.任务列表 4.下单列表
            #流程1.quant如果任务没运行，先让web停止10秒发送协议

            #1.设置数据
            userName = g_config.info("username")
            api = g_config.marketsApi()

            return
        def initMarketTrends():
            return
        def startFile():
            return
        def backtesting():
            return
        def orders():
            return
        def saveConfig():#保存设置
            g_config.setConfig(msg)
            g_config.saveFile()
            #todo:是否服务器
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
        # id = msg.get('id', None)
        # args = msg.get('args', [])
        print(f"~~~~~~~~~~[消息处理]~~~~~~~~ 消息ID: {id}, 参数: {msg}")
        rt = self.idTransform(id,msg)
        return 0