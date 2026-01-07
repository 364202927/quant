from server.utils.decoratorTool import singleton
from server.utils.fileConfig import g_config
from server.utils.common import require


@singleton
class marketMgr:
    '交易所管理器'
    __exchangeMgr = None

    def init(self):
        self.__exchangeMgr = {}
        for name in g_config.markets():
            market_config = g_config.markets()[name]
            if market_config['enable'] == 1:
                g_marketMgr._newExchange(name, market_config)

    def _newExchange(self, exName, config):
        exchange = require(
            'server.market.' + config['exchange']
        )(config['description'])
        exchange._id = exName
        exchange.enroll(config)
        self.__exchangeMgr[exName] = exchange
        print('激活的交易所：{}, 说明：{}'.format(exName, config['description']))

    def get(self, keyName: str = ""):
        if keyName == "":
            return self.__exchangeMgr
        return self.__exchangeMgr[keyName]
    

g_marketMgr = marketMgr()
