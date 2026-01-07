from server.market import g_marketMgr
from server.utils import pdData, switchFn, switchV, slit, inRange, binanceTimestamp, err

kBuy = 'buy'
kSell = "sell"
kLong = 'LONG'
kShort = 'SHORT'
kMONEY = 90  # 默认每次下单为仓位的90%
kORDERBOOK = 1  # 默认以订单本的第二个下单，如市价下单选0
kMAX_ORDERBOOK = 5  # 订单本最大值

# trades 近期成交

# todo:默认风险管理,例如设定止损下限，每天交易次数，杠杆控制
# todo:币本位没做


class baseTrade:
    "交易基类"

    __lv = 1  # 杠杆
    ex = None  # 交易所
    # todo:同一种币下单方式是单向或双向
    _openOrders, _history = None, None  # 当前挂单，历史挂单

    def __init__(self, exName, lv=1):
        self.setEx(exName)
        self.setLv(lv)
        self._setHeadFile()

    def _setHeadFile(self):
        self._openOrders = pdData(
            head=['time', 'symbol', 'orderId', 'positionSide',
                  'holdAmt', 'leverage', 'total']
        )  # 订单检测(time,类型_币种,id,方向side_pos, 持仓数量)
        self._history = pdData(
            head=['time', 'lastTime', 'symbol', 'orderId', 'positionSide',
                  'total', 'amount', 'average', 'leverage', 'fee(BNB)']
        )  # 顺序记录每一笔操作历史

    # 向交易所下单
    def _order(self, symbol, bet, dir, posSide='', orderBook=kORDERBOOK):
        acc = self.ex.account()  # 刷新账户余额
        category, symbolInfo = self.ex.coinInfo(symbol)
        res = self.ex.get('ccxt').fetch_order_book(
            symbol=symbolInfo.get('id'),
            limit=kMAX_ORDERBOOK)  # bids买单从高到低 asks卖单从低到高
        price = dir == kBuy and res['bids'][orderBook][0] or res['asks'][(
            kMAX_ORDERBOOK - 1) - orderBook][0]
        # print("~~~_order~~~",res['bids'],res['asks'], price, self.ex.tickerPrice(symbol)['price'])
        coin = self.ex.accFree(category == 'spot')
        if category == 'spot' and dir == kSell:  # 现货出售
            coin, _ = slit(symbolInfo['id'], 'USDT')
            accAmount = self.ex.get('acc')['free'].get(coin)  # 账号余额
            if accAmount is None:
                return False
            coin = accAmount * price
        totalBet = coin * (bet * 0.01)
        amount = round(totalBet / price, 2)
        print('~~~~_order~~~~~~', bet, coin)
        if not inRange([symbolInfo['cost']['min'],
                       symbolInfo['cost']['max']], totalBet):
            err('下单资金异常:{}, 范围是:{} ~ {}'.format(
                totalBet, symbolInfo['cost']['min'], symbolInfo['cost']['max']))
            return False
        print("总资金:{},单价:{},数量:{}".format(totalBet, price, amount))
        # 下单为市价吃单，不走挂单
        return self.ex.order(
            state=dir,
            symbol=symbol,
            amount=amount,
            lv=self.__lv,
            posSide=posSide)
    # 永续合约

    def _futures(self, symbol, dir, positionSide, bet, orderBook):
        pf = self._updateSymbol(symbol, positionSide)
        rt = self._order(symbol, bet, dir, positionSide, orderBook)
        rt['lv'] = self.__lv
        if len(pf) > 0:
            rt['time'] = pf.iloc[0]['time']
        self._updateOrder(symbol, '{}_{}'.format(dir, positionSide), rt)
        # 下单成功
        if rt.get('status') == 'closed':
            rt['status'] = 'open'
            if len(pf) > 0:  # 删掉旧记录从新加载
                rt['time'] = pf.iloc[0]['time']
                rt['origQty'] = float(rt['origQty']) + \
                    float(pf.iloc[0]['holdAmt'])
                self._openOrders.remove(pf.index)
            self._updateOrder(symbol, positionSide, rt)

    # 获取记录的单子数据
    def _findOrder(self, symbol, positionSide):
        orders = self._openOrders.get()
        pf = orders[(orders['symbol'] == symbol) & (
            orders['positionSide'] == positionSide)]
        return pf
    # 查找单子并更新状态

    def _updateSymbol(self, symbol, positionSide):
        pf = self._findOrder(symbol, positionSide)
        if pf.empty or \
                (len(pf) > 0 and pf.iloc[0]['holdAmt'] != 'open'):
            return pf
        # 单子是委托，从交易所更新，状态改变更新数据
        index, pf = pf.index, pf.iloc[0]
        if pf['holdAmt'] == 'open':
            rt = self.ex.order('find', symbol=symbol, orderId=pf['orderId'])
            if rt.get('status') == 'open':
                return []
            self._setOpenAmt(index, rt.get('status') ==
                             'cancel' and 'cancel' or rt['origQty'])
            # 挂单正常转为仓位
            if rt.get('status') != 'cancel':
                transform = {'sell_SHORT': kShort, 'buy_LONG': kLong}
                self._openOrders.get().loc[index, 'positionSide'] = transform.get(
                    pf['positionSide']) or pf['positionSide']
                self._openOrders.get().loc[index, 'total'] = switchV(
                    rt, 'cost', 'cumQuote')
                rt['lv'] = pf['leverage']
                self._updateOrder(symbol, positionSide, rt)
            return self._findOrder(symbol, positionSide)
    # 根据单子返回数据 更新_openOrders和_history

    def _updateOrder(self, symbol, dir, rtData):
        # print("~~~~_updataOrder~~~~~", rtData)
        params = {'time': switchV(rtData, 'time', 'lastUpdateTimestamp'),
                  'orderId': rtData.get('orderId'),
                  'symbol': symbol,
                  'positionSide': dir,
                  'total': switchV(rtData, 'cost', 'cumQuote'),
                  'leverage': rtData.get('lv')}

        def open():
            params['holdAmt'] = rtData.get(
                'origQty') == -1 and 'open' or rtData.get('origQty')
            self._openOrders.dataConcat(params)

        def close():
            params['lastTime'] = switchV(
                rtData, 'lastTradeTimestamp', 'updateTime')
            params['amount'] = switchV(rtData, 'amount', 'origQty')
            params['average'] = switchV(rtData, 'average', 'avgPrice')
            params['fee(BNB)'] = rtData.get('fee_Bnb')
            self._history.dataConcat(params)
            # 单子是现货，去掉监控
            category, _ = slit(symbol, '_')
            if category == 'spot':
                # print("~~~现货~~~~~", rtData)
                pf = self._openOrders.get()
                self._openOrders.remove(
                    pf[pf['orderId'] == rtData['id']].index)
        switchFn({'open': open,
                  'closed': close},
                 key=rtData.get('status'))

    def _setOpenAmt(self, index, value):
        self._openOrders.get().loc[index, 'holdAmt'] = value

    #
    def setLv(self, lv):
        self.__lv = lv

    def setEx(self, name):
        self.ex = g_marketMgr.get(name)

    def exName(self):
        return self.ex

    def getKline(self, symbol, strStartTime, timeframe='5m'):  # todo:不要
        return self.ex.getKline(
            symbol, [strStartTime, 'now'], timeframe=timeframe)

    def ticker(self, symbol, timeframe='5m'):  # todo:不要
        return self.ex.ticker(symbol, timeframe)

    def updateTicker(self, symbol, pd, timeframe='5m', limit=100):  # 更新k线，并根据限制返回数据, todo:不要
        new_kLine = self.ticker(symbol, timeframe)
        pd.pfConcat(new_kLine)
        kLine = pd.get()
        return kLine[len(kLine) - limit:]
    # 将k线数据更新到最新

    def updateHistory(self, symbol, fileName, save=True):  # todo:不要
        kLine = pdData()
        kLine.readFile(fileName)
        last = self.ex.getHistoryCandles(
            symbol, [kLine.get().iloc[-1]['candle_begin_time'], 'now'])
        kLine.pfConcat(last)
        if save:
            kLine.save2File(fileName)
        return kLine.get()
    # 修复k线数据

    def repairKline(self, symbol, fileName):  # todo:不要
        return 0
    # 更新持仓

    def updateTrade(self):
        symbolList, delList = [], []
        acc = self.ex.account()
        positionList = self.ex.checkPosition()
        openOrders = self._openOrders.get()
        for i in range(len(openOrders)):
            pf = openOrders.iloc[i]
            # 挂单检测
            if pf['holdAmt'] == 'open':
                pf = self._updateSymbol(pf['symbol'], pf['positionSide'])
                if len(pf) == 0:
                    continue
                pf = pf.iloc[0]  # 挂单被手动取消
                if pf['holdAmt'] == 'cancel':
                    delList.append(i)
                    continue
            # 获取单子当前状态
            _, symbolInfo = self.ex.coinInfo(pf['symbol'])
            # print("~~~~updateTrade~~~~~", pf['positionSide'])
            rt = [item for item in positionList if item["symbol"] == symbolInfo.get(
                'id') and item["positionSide"] == pf['positionSide']]
            # 正常仓位检测
            if len(rt) > 0:
                rt[0]['total'] = pf['total']
                self._openOrders.get().loc[i, 'leverage'] = rt[0]['leverage']
                symbolList.append(rt[0])
                continue
            # 仓位被手动平仓，使用orderid再次查询，重设状态
            rt = self.ex.order(
                'find',
                symbol=pf['symbol'],
                orderId=pf['orderId'])
            # print("单子以删除，旧单子数据",rt)
            rt['time'], rt['updateTime'], rt['lv'] = pf['time'], binanceTimestamp(
            ), pf['leverage']
            self._updateOrder(
                pf['symbol'], '{}_{}'.format(
                    'fix', pf['positionSide']), rt)
            delList.append(i)
        # 若单子被手动删掉，则同步到_openOrders
        for index in delList:
            self._openOrders.remove(index)
        return symbolList

    def show(self, status='normal', value=0):
        def normal():
            print("~~~检测记录~~~~~")
            self._openOrders.show()
            print("~~~历史记录~~~~~")
            self._history.show()

        def futures():
            order = value
            print("合约:{}_{}_{}x   开仓价:{}   标记价:{}   强平价:{}   数量:{}     浮盈亏:{}({}%)".format(
                # 方向_symbol_lv
                order['positionSide'], order['symbol'], order['leverage'],
                order['entryPrice'],  # 开仓价
                order['markPrice'],  # 标记价
                order['liquidationPrice'],  # 强平
                abs(float(order['positionAmt'])),  # 持仓数量
                order['unRealizedProfit'],  # 未平仓盈亏
                round(float(order['unRealizedProfit']) / float(order['total']) * 100), 2))  # 百分比

        return switchFn({'normal': normal,
                        'futures': futures},
                        key=status)

    # usdt转换为bet
    def u2Bet(self, symbol, usdt):
        category, _ = self.ex.coinInfo(symbol)
        free_usdt = self.ex.accFree(category == 'spot')
        if usdt > free_usdt:
            return 100
        # print(free_usdt, usdt, usdt / free_usdt)
        return (symbol, round(usdt * 100 / free_usdt, 2))

    # 撤销挂单
    def cancal(self, symbol, positionSide):
        pf = self._findOrder(symbol, positionSide)
        if len(pf) <= 0:
            return
        rt = self.ex.order(
            state='cancel',
            symbol=symbol,
            orderId=pf.iloc[0]['orderId'])
        if rt['status'] == 'CANCELED':
            self._openOrders.remove(pf.index)
    # 现货根据账户百分比下单,默认用90%的仓位

    def buy(self, symbol, bet=kMONEY, usdt=0, orderBook=0):
        if usdt > 0:
            _, bet = self.u2Bet(symbol, usdt)
        rt = self._order(symbol, bet, kBuy, '', orderBook)
        self._updateOrder(symbol, kBuy, rt)

    def sell(self, symbol, bet=kMONEY, orderBook=0):
        print("~~~~~sell~~~~~", symbol)
        rt = self._order(symbol, bet, kSell, '', orderBook)
        if not rt:
            print('账号不存在币：', symbol)
            return
        self._updateOrder(symbol, kSell, rt)

    # 合约，u本位(bet是闲置u比例)
    def openLong(self, symbol, bet=kMONEY, usdt=0, orderBook=kORDERBOOK):
        print("~~~~openLong~~~~~", symbol)
        if usdt > 0:
            _, bet = self.u2Bet(symbol, usdt)
        self._futures(symbol, kBuy, kLong, bet, orderBook)

    def openShort(self, symbol, bet=kMONEY, usdt=0, orderBook=kORDERBOOK):
        if usdt > 0:
            _, bet = self.u2Bet(symbol, usdt)
        print("~~~~openShort~~~~~", symbol)
        self._futures(symbol, kSell, kShort, bet, orderBook)
    # 平仓

    def closePos(self, symbol, positionSide, bet=100):
        pf = self._updateSymbol(symbol, positionSide)  # 查找检测单的数据，若是挂单再检测一次
        print('~~~~closePos~~~~~~~', symbol, positionSide)
        if len(pf) == 0:
            print("平仓失败,没有该币持仓", symbol, positionSide)  # todo:可改为撤销订单
            return
        pf = pf[pf['holdAmt'] != 'open']  # 忽略掉挂单状态
        index = pf.index
        pf = pf.iloc[0]
        dir = positionSide == kLong and kSell or kBuy
        amt = float(pf['holdAmt']) * (bet * 0.01)
        # print("~~~~平仓~~~", dir, amt)
        rt = self.ex.order(
            state=dir,
            symbol=symbol,
            amount=amt,
            posSide=positionSide)
        rt['time'], rt['lv'] = pf['time'], pf['leverage']
        self._updateOrder(symbol, '{}_{}'.format(dir, positionSide), rt)
        # 刷新个数
        newAmt = float(pf['holdAmt']) - float(rt['origQty'])
        self._setOpenAmt(index, newAmt)
        if newAmt <= 0:
            self._openOrders.remove(index)
