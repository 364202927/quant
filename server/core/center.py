from server.utils.decoratorTool import singleton
from server.market.markets import g_marketMgr


# todo:每天记录当天的资金
# 统计，用户全部资产，记录买入价，均价，持仓


@singleton
class center:
    '用户数据中心'
    # 总资金
    _usedBook = {}  # 用户数据 exName = {obj, account账号信息}

    def init(self):
        # todo读取记录
        g_marketMgr.init()
        markets = g_marketMgr.get()
        for ex in markets:
            self._usedBook[ex] = {'obj': markets[ex], 'acc': ''}
        self.updateAcc()

    # 刷新用户账号资金
    def updateAcc(self):
        for exName in self._usedBook:
            obj = self._usedBook[exName]['obj']
            self._usedBook[exName]['acc'] = obj.account()

    # todo:保存所有task的状态
    def update(self):
        pass

    # def get(self, key):
        # return switch({'acc': self._info['acc'],  # 交易所账号信息
        #             },
        #           key=key)
        # pass

    def show(self):
        for ex in self._usedBook:
            print('交易所:{}   数据:{}'.format(ex, self._usedBook[ex]['acc']))


g_userCenter = center()

# {'total': {'spot_BNB': 0.02822835, 'spot_USDC': 1.69849, 'spot_LDBNB': 0.49867017, 'spot_LDUSDT': 8642.75864108, 'spot_LDUSDC': 2577.61859469, 'spot_IO': 0.45859617, 'BNB': '0.02718221', 'USDT': '1132.28059997'},
#  'used': {'BNB': '0.00000000', 'USDT': '0.00000000'},
#  'free': {'spot_BNB': 0.02822835, 'spot_USDC': 1.69849, 'spot_LDBNB': 0.49867017, 'spot_LDUSDT': 8642.75864108, 'spot_LDUSDC': 2577.61859469, 'spot_IO': 0.45859617, 'BNB': '0.02718221', 'USDT': '1132.28059997'}}
