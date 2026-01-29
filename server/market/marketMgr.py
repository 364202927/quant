from server.utils import singleton, g_config, require
# todo:使用堆栈的方式进行下单交易

@singleton
class marketMgr:
    '交易所管理器'

    def init(self):
        self.__exchangeMgr = {}
        #创建交易所
        for name in g_config.marketsApi():
            market_config = g_config.marketsApi()[name]
            if market_config['enable'] == 1:
                self._newExchange(name, market_config)
        if len(self.__exchangeMgr) == 0:
            print("~~~~~没有交易所激活~~~~~~")
        #todo:接收下单信息

    def _newExchange(self, exName, config):
        exchange = require('server.market.' + config['exchange'])(config['description'])
        exchange._id = exName
        exchange.enroll(config)
        self.__exchangeMgr[exName] = exchange
        print('激活的交易所：{}, 说明：{}'.format(exName, config['description']))

    def get(self, keyName: str = ""):
        if keyName == "":
            return self.__exchangeMgr
        return self.__exchangeMgr[keyName]

    def run(self):
        pass
    

g_marketMgr = marketMgr()
