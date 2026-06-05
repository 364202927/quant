from server.utils import evtConnect, kEvt_Market, switchFn, pdData, recordBuffer
from server.market import eMarketId

class storageOrders:
    "订单/状态事件 监听"

    def __init__(self):
        self.__holdings: dict[str, list] = {}   # 交易所现持有的原始订单数据
        self.__taskOrders = recordBuffer()          # task保存的所有订单
        #todo:读取__taskOrders保存的文件
        evtConnect(kEvt_Market, self)

    def evtProcess(self, key, *args):
        id, exName = args[0], args[1]
        # 持仓记录
        def _initHoldings():
            key, data = args[2],args[3]
            self.__holdings.setdefault(exName, {}).setdefault(key, {}).update(data)
            print("~~~_initHoldings~~~~~~", self.__holdings)
        
        switchFn({eMarketId['positions']: _initHoldings,
                    }, key=id)