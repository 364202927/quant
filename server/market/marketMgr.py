from server.utils import singleton, g_config, require, err, log,warn,tryCatch,logFormat

@singleton
class marketMgr:

    def init(self):
        self.__exchangeMgr: dict = {}
        self.__user: dict = {'all': {}}
        markets = g_config.marketsApi()
        for name, config in markets.items():
            if config['enable'] == 1:
                self._newExchange(name, config)
        if not self.__exchangeMgr:
            warn("~~~~~没有交易所激活~~~~~~")

    def _newExchange(self, exName: str, config: dict) -> None:
        exchange = require('server.market.' + config['exchange'])(config['description'])
        exchange.enroll(config)
        self.__exchangeMgr[exName] = exchange
        market = self.__exchangeMgr[exName].markets()
        print(f"激活交易所：{exName}, 说明：{config['description']}")
        print(market)


    def get(self, keyName: str = ""):
        if not keyName:
            return self.__exchangeMgr
        return self.__exchangeMgr[keyName]
    
    #获取交易所
    def userAccount(self, exName: str = "", isUpdate: bool = False) -> dict:
        if not isUpdate:
            return self.__user['all'] if not exName else self.__user.get(exName, {})

        # 拉取目标交易所账户
        targets = [exName] if exName else list(self.__exchangeMgr)
        for name in targets:
            ex = self.__exchangeMgr.get(name)
            self.__user[name] = ex.account()

        # 重新汇总全部交易所余额
        summary = {key: {} for key in ('total', 'used', 'free')}
        for name in self.__exchangeMgr:
            acc = self.__user.get(name)
            for key in summary:
                for coin, val in acc[key].items():
                    if val and float(val) > 0:
                        summary[key][coin] = summary[key].get(coin, 0) + float(val)
        self.__user['all'] = summary
        log("账户数据已更新, 交易所数量:", len(targets))
        # logFormat(self.__user)
        return summary

    def run(self):
        pass


g_marketMgr = marketMgr()
