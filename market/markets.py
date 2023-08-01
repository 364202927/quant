from include import *
from data.user.center import g_userCenter

@singleton
class marketMgr:
    '交易所管理器'
    __exchangeMgr = None

    def __init__(self):
        self.__exchangeMgr = {}

    def newExchange(self, keyName, exName, apiKey, secret, description):
        exchange = require('market.' + exName)(description)
        exchange.enroll(apiKey, secret)
        self.__exchangeMgr[keyName] = exchange
        #初始化交易所数据
        g_userCenter.initRecord(exchange)
        # exchange.showApi()
        # logFormat(exchange.account())
        # exchange.account()

    def getExchange(self, keyName: str = ""):
        if keyName == "":
            return self.__exchangeMgr
        return self.__exchangeMgr[keyName]


g_marketMgr = marketMgr()