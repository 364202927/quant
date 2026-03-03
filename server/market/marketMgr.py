from server.utils import singleton, g_config, require, err, log,warn,tryCatch,logFormat
from server.market.baseExchange import *

@singleton
class marketMgr:

    def init(self):
        self.__exchangeMgr: dict = {}   #保存的交易所
        self.__user: dict = {'all': {}} #全交易所个人数据统计
        for name, config in  g_config.marketsApi().items():
            if config['enable'] == 1:
                self._newExchange(name, config)
        if not self.__exchangeMgr:
            warn("~~~~~没有交易所激活~~~~~~")

    def _newExchange(self, exName: str, config: dict) -> None:
        exchange = require('server.market.' + config['exchange'])(config['description'])
        exchange.enroll(config)
        self.__exchangeMgr[exName] = exchange
        markets = self.__exchangeMgr[exName].markets()
        print(f"激活交易所：{exName}, 说明：{config['description']}")
        # for k,v in markets.items():
        #     print('~~~~~type~~~~', k)
        # print(markets['swap'])
        # exit()

    def get(self, keyName: str = "")->baseExchange:
        if not keyName:
            return self.__exchangeMgr
        return self.__exchangeMgr[keyName]
    
    #获取交易所
    def userAccount(self, exName: str = "", isUpdate: bool = False) -> dict:
        if not isUpdate:
            return self.__user['all'] if not exName else self.__user.get(exName, {})
        # 更新交易所
        targets = [exName] if exName else list(self.__exchangeMgr)
        for name in targets:
            ex = self.__exchangeMgr.get(name)
            self.__user[name] = ex.account()
        # 统计全交易所
        summary = {}
        for name in self.__exchangeMgr:
            acc = self.__user.get(name)
            for coin, val in acc['total'].items():
                summary[coin] = summary.get(coin, 0) + float(val)
        self.__user['all'] = summary
        log("账户数据已更新, 交易所数量:", len(targets))
        # logFormat(self.__user)
        return summary

    def run(self):
        pass


g_marketMgr = marketMgr()
