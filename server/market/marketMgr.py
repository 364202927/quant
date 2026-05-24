import asyncio
from server.utils import g_config, require, err, log, warn, tryCatch, logFormat, evtConnect, kEvt_Market
from server.market.baseExchange import baseExchange
from server.external.interface import ExternalInterface


class marketMgr(ExternalInterface):

    def __init__(self, fnHandler=None):
        # super().__init__(fnHandler)
        self.__exchangeMgr: dict = {}
        self.__user: dict = {'all': {}}
        for name, config in g_config.marketsApi().items():
            if config.get('enable') == 1:
                self._newExchange(name, config)
        if not self.__exchangeMgr:
            warn("~~~~~没有交易所激活~~~~~~")
        evtConnect(kEvt_Market, self)

    def _newExchange(self, exName: str, config: dict) -> None:
        exchange = require('server.market.' + config['exchange'])(config['description'])
        exchange.enroll(config)
        self.__exchangeMgr[exName] = exchange
        markets = self.__exchangeMgr[exName].markets()
        print(f"激活交易所：{exName}, 说明：{config['description']}")

    def get(self, keyName: str = "") -> baseExchange:
        if not keyName:
            return self.__exchangeMgr
        return self.__exchangeMgr[keyName]

    def userAccount(self, exName: str = "", isUpdate: bool = False) -> dict:
        if not isUpdate:
            return self.__user['all'] if not exName else self.__user.get(exName, {})
        targets = [exName] if exName else list(self.__exchangeMgr)
        for name in targets:
            ex = self.__exchangeMgr.get(name)
            self.__user[name] = ex.account()
        summary = {}
        for name in self.__exchangeMgr:
            acc = self.__user.get(name)
            for coin, val in acc['total'].items():
                summary[coin] = summary.get(coin, 0) + float(val)
        self.__user['all'] = summary
        log("账户数据已更新, 交易所数量:", len(targets))
        return summary

    def evtProcess(self, key, *args):
        pass

    async def run(self) -> None:
        if not self.__exchangeMgr:
            return
        tasks = [ex.run() for ex in self.__exchangeMgr.values()]
        await asyncio.gather(*tasks)
