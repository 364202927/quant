from strategy.base.baseTrade import *

# todo:冷静期


class testTrade(baseTrade):
    "测试交易"

    lossLine = 0  # 止损线

    def __init__(self, exName, lv=1):
        super().__init__(exName, lv)
        self._setHeadFile()
        self.lossLine = 3  # 默认亏损线
        # head = ['time', 'symbol', 'orderId', 'positionSide', 'holdAmt','leverage','total'] # 订单检测(time,类型_币种,id,方向side_pos, 持仓数量)
        # head = ['time', 'lastTime','symbol', 'orderId', 'positionSide',
        # 'total', 'amount', 'average', 'leverage','fee(BNB)']
        # #顺序记录每一笔操作历史(开仓时间, 最后操作,'symbol', 'orderId', 'positionSide',
        # total'使用的资金', 'amount(个数)', 'average(平仓价)',
        # 'leverage','fee(BNB手续费)','profit(盈亏)')

    # 查询持仓，盈利百分比
    def checkPosition(self, autoClose=False):
        openOrders = self._openOrders.get()
        # if not openOrders or openOrders.empty:
        #     return []
        if not openOrders or \
                openOrders.empty or\
                autoClose == False:
            return self._openOrders
        # 风险控制,止盈止损
        closePosIndex = []
        size = len(self._openOrders.get())
        for i in range(len(self._openOrders.get())):
            data = self._openOrders.get(cols=i)
            # 检测持仓是否触发止损平仓
            profit = floatingProfit(
                float(
                    data['orderId']), float(
                    self.ex.tickers(
                        data['symbol'])['price']), data['positionSide'])
            if profit <= self.lossLine:
                closePosIndex.append({'symbol': data['symbol'],
                                      'pos': data['positionSide']})

        for index in closePosIndex:
            self.closePos(index['symbol'], index['pos'])
        return self._openOrders

    # ~~~~~~合约开单~~~~~~~~
    def openLong(self, symbol, bet=kMONEY, usdt=0, orderBook=kORDERBOOK):
        bidPrice = self.ex.bookTickers(symbol)  # ['bidPrice']
        self._openOrders.dataConcat({'time': bidPrice['time'],
                                     'symbol': symbol,
                                     'orderId': bidPrice['bidPrice'],
                                     'positionSide': kLong,
                                     "holdAmt": 0,
                                     'leverage': 1,
                                     'total': 1})
        print("~~~~open long~~~~", symbol, bidPrice)

    def openShort(self, symbol, bet=kMONEY, usdt=0, orderBook=kORDERBOOK):
        bidPrice = self.ex.bookTickers(symbol)  # ['bidPrice']
        self._openOrders.dataConcat({'time': bidPrice['time'],
                                     'symbol': symbol,
                                     'orderId': bidPrice['bidPrice'],
                                     'positionSide': kShort,
                                     "holdAmt": 0,
                                     'leverage': 1,
                                     'total': 1})
        print("~~~~open short~~~~", symbol, bidPrice)
    # 平仓

    def closePos(self, symbol, positionSide, bet=100):
        openOrders = self._openOrders.get()
        mask = (openOrders['symbol'] == symbol) & (
            openOrders['positionSide'] == positionSide)
        openOrdersData = openOrders[mask]
        if openOrdersData.empty:
            return
        print("~~~~close pos~~~~", symbol, positionSide)
        price = self.ex.tickers(symbol)
        self._history.dataConcat(
            {
                'time': openOrdersData['time'].iloc[0],
                "lastTime": price['time'],
                'symbol': symbol,
                'orderId': openOrdersData['orderId'].iloc[0],
                'positionSide': openOrders['positionSide'].iloc[0],
                'total': 1,
                'amount': 1,
                'average': price['price'],
                'leverage': 1,
                'fee(BNB)': 1})
        self._openOrders.remove(openOrdersData.index[0])
    # ~~~现货开单~~~

    def buy(self, symbol, bet=kMONEY, usdt=0, orderBook=0):
        print("~~~test buy~~~~~", symbol)

    def sell(self, symbol, bet=kMONEY, orderBook=0):
        print("~~~~~test sell~~~~~", symbol)
