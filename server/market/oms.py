from server.utils import evtConnect, evtFireAsync, kEvt_Market, log, switchFn, evtFire, slit, division,inRange,warn
from server.market import eMarketId, kSpot, kSwap, kBuy, kSell,kPm,kClose
from server.market.baseExchange import baseExchange

class oms:
    "本地订单管理：拆分/合并/本地余额校验,全订单必须走这个类"

    def __init__(self, exFn=None):
        self._localFree = evtFire(kEvt_Market, eMarketId['gBalance'])  # 本地缓存的 center 数据
        self._getEx = exFn            # exName → baseExchange
        evtConnect(kEvt_Market, self)

    def evtProcess(self, key, *args):
        id_ = args[0]
        def _oms():
            data = args[1] if len(args) > 1 else {}
            orderType = data.get('type', '')
            direction = data.get('dir', '')
            isPm = orderType == kSwap

            # 1. 校验 + 准备参数 (价格/数量)
            result = self._checkOrder(data, isPm)
            if result is not True:
                warn(f"[oms] 拦截: {result}")
                return

            # 2. 余额处理
            isClose = direction == kClose or (direction == kSell and not isPm)
            if isClose:
                self._close(data)
            else:
                # 买入/开仓: 扣减 consumeCoin 余额
                fixTotel = data.get('price', 0) * data.get('amount', 0)
                localData = self._localCoin(data.get('exName'), isPm)
                consumeCoin = data.get('consumeCoin', 'USDT')
                if localData.get(consumeCoin, 0) < fixTotel:
                    warn(f"下单金额不足: {fixTotel}, 余额: {localData.get(consumeCoin, 0)}")
                    return
                localData[consumeCoin] -= fixTotel

            # 3. 记录 + 发送
            self._send(data)

        switchFn({eMarketId['oms']: _oms}, key=id_)

    # ── 当前挂单最优价 ──
    def _BBO(self, ex: baseExchange, symbol: str, dir: str, order: int) -> float:
        book = ex.orderBook(symbol, limit=5)
        target = book['bids'] if dir in (kBuy, 'buy') else book['asks']
        return target[order][0]

    # 更新本地数据
    def _localCoin(self, exName:str, isPm:bool, coin:str = ''):
        trageEx = ''
        for k,v in self._localFree.items():
            for ex,it in v.items():
                if ex == exName:
                    trageEx = it
                    break
        key = isPm == True and kPm or 'free'
        if coin == '':
            return trageEx.get(key)
        return trageEx.get(key).get(coin)

    # ── 校验订单 + 准备价格/数量 ──
    def _checkOrder(self, data: dict, isPm: bool):
        exName = data.get('exName', '')
        symbol = data.get('symbol', '')
        direction = data.get('dir', '')
        totelPrice = data.get('totelPrice', 0)
        orderPrice = data.get('price')
        orderBook = data.get('orderBook', 0)
        symbolInfo = data.get('coinInfo')
        amount = data.get('amount')
        consumeCoin = data.get('consumeCoin')
        ex = self._getEx(exName)

        # 获取币种信息
        if symbolInfo is None and ex:
            _, symbolInfo = ex.coinInfo(symbol)
            data['coinInfo'] = symbolInfo

        step = symbolInfo.get('step') if symbolInfo else None

        # 卖出现货 (绕过 preTrade, 需自行处理 consumeCoin/bet)
        if direction == kSell and not isPm:
            if consumeCoin is None:
                _, newSymbol = slit(symbol, '_')
                consumeCoin = newSymbol.split('/')[0] if '/' in newSymbol else ''
                data['consumeCoin'] = consumeCoin

            localCoin = self._localCoin(exName, False, consumeCoin)

            # bet 转换: 卖出 bet:100 → 100% 持仓量
            if isinstance(totelPrice, str) and totelPrice.startswith('bet:'):
                proportion = float(totelPrice[4:]) * 0.01
                amount = proportion * localCoin
                data['amount'] = amount
                if orderPrice is None and orderBook >= 0 and ex:
                    orderPrice = self._BBO(ex, symbol, direction, orderBook)
                    data['price'] = orderPrice
                if orderPrice:
                    data['totelPrice'] = orderPrice * amount

            if amount and localCoin < amount:
                return f"卖出余额不足: 需要 {amount}, 持有 {localCoin}"

        # 获取 BBO 价格 (非卖出已处理的情况)
        if orderPrice is None and orderBook >= 0 and ex:
            orderPrice = self._BBO(ex, symbol, direction, orderBook)
            data['price'] = orderPrice

        # 计算数量
        if amount is None and orderPrice:
            amount = division(totelPrice, orderPrice, step)
            data['amount'] = amount

        # 校验取值范围
        if symbolInfo:
            if amount and not inRange([symbolInfo['amount'].get('min'), symbolInfo['amount'].get('max')], amount):
                return f"amount 取值范围: {symbolInfo['amount']}, 当前: {amount}"
            if orderPrice and not inRange([symbolInfo['price'].get('min'), symbolInfo['price'].get('max')], orderPrice):
                return f"price 取值范围: {symbolInfo['price']}, 当前: {orderPrice}"

        # 平仓合约: 检查持仓
        if direction == kClose:
            positions = evtFire(kEvt_Market, eMarketId['gPosit'], 'ex', symbol)
            if not positions or exName not in positions:
                return f"未找到持仓: {symbol} @ {exName}"
            data['_positions'] = positions[exName]

        return True

    # ── 平仓/卖出 ──
    def _close(self, data: dict):
        direction = data.get('dir', '')
        isPm = data.get('type', '') == kSwap
         # 卖现货: 扣减币余额
        if direction == kSell and not isPm:
            localData = self._localCoin(data.get('exName'), False)
            consumeCoin = data.get('consumeCoin', '')
            localData[consumeCoin] -= data.get('amount', 0)
            return
        # elif direction == kClose:
        # 平仓合约: 从持仓数据设置反向
        positions = data.pop('_positions', [])
        if positions:
            pos = positions[0]
            posSide = pos.get('side', '')
            if posSide == 'LONG':
                data['posSide'] = 'SHORT'
            elif posSide == 'SHORT':
                data['posSide'] = 'LONG'
            data['amount'] = float(pos.get('contracts', data.get('amount', 0)))

    # ── 记录 + 发送 ──
    def _send(self, data: dict):
        # print('~~~send~~~~', data)
        #  记录订单详情,用orders.py记录
            # orderDetail = {
            #     'time': time.time(),
            #     'taskName': taskName,
            #     'symbol': symbol,
            #     'type': orderType,
            #     'dir': direction,
            #     'totelPrice': totelPrice,
            #     'price': orderPrice,
            #     'amount': amount,
            #     'exName': data.get('exName', ''),
            #     'status': 'pending',
            # }
            # self._taskOrders.setdefault(taskName, []).append(orderDetail)

        evtFireAsync(kEvt_Market, eMarketId['order'], data)

    def splitOrder(self):
        # c. 若单子金额过大,需要进行拆分(冰山单)
        # if totelPrice > symbolInfo['cost'].get('max'): totelPrice = symbolInfo['cost'].get('max')
        pass