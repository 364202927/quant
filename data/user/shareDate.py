from include import *
from market.markets import g_marketMgr

@singleton
class shareDate:
    '共享数据'
    _origKlines = {}
    
    def regSymbols(self, exName, symbolOrTab):
        if not self._origKlines.get(exName):
            self._origKlines[exName] = {}
        if isinstance(symbolOrTab, list):
            # todo 交易所的symbol存在则不初始化
            for symbol in symbolOrTab:
                self._origKlines[exName][symbol]=None
        else:
            self._origKlines[exName][symbolOrTab] = None

        #todo初始化k线数据
        # 1.先从文件读取，没有数据报错
        # 2.文件数据再整合,缺少的再拉数据获取

    # 更新全部k线
    def update(self):
        print("~~~~~~shareDate~~~~~~",self._origKlines,g_marketMgr)
        pass

    def getKline(self, exName, symbol):
        pass

g_share = shareDate()