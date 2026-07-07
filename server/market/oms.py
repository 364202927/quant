from decimal import Decimal, ROUND_DOWN
from server.utils import evtConnect, evtFireAsync, kEvt_Market, log, switchFn, evtFire, slit, division,inRange,warn
from server.market import eMarketId, kSpot, kSwap, kBuy, kSell,kPm,kClose,kCancel,kLong,kShort
from server.market.baseExchange import baseExchange

class oms:
    "本地订单管理：拆分/合并/本地余额校验,全订单必须走这个类"

    def __init__(self, exFn=None):
        self._localFree = evtFire(kEvt_Market, eMarketId['gBalance']) or {}  # 本地缓存的 center 数据
        self._getEx = exFn            # exName → baseExchange
        evtConnect(kEvt_Market, self)

    def evtProcess(self, key, *args):
        id_ = args[0]
        def _balanceUpdate():
            exId = args[1] if len(args) > 1 else ''
            account = args[2] if len(args) > 2 else ''
            data = args[3] if len(args) > 3 else {}
            if exId and account and isinstance(data, dict):
                target = self._localFree.setdefault(exId, {}).setdefault(account, {})
                self._mergeBalance(target, self._cleanBalanceData(data))
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

            if orderType == kCancel:
                self._send(data)
                return

            # 2. 余额处理
            isClose = direction == kClose or (direction == kSell and not isPm)
            if isClose:
                self._close(data)
            else:
                # 买入/开仓: 扣减 consumeCoin 余额
                fixTotel = data.get('price', 0) * data.get('amount', 0) or data.get('totelPrice', 0)
                localData = self._localCoin(data.get('exName'), isPm)
                consumeCoin = data.get('consumeCoin', 'USDT')
                if localData.get(consumeCoin, 0) < fixTotel:
                    warn(f"下单金额不足: {fixTotel}, 余额: {localData.get(consumeCoin, 0)}")
                    return
                localData[consumeCoin] -= fixTotel

            # 3. 记录 + 发送
            self._send(data)

        switchFn({eMarketId['oms']: _oms,
                  eMarketId['balance']: _balanceUpdate,
                  eMarketId['wsBalance']: _balanceUpdate}, key=id_)

    # ── 当前挂单最优价 ──
    def _BBO(self, ex: baseExchange, symbol: str, dir: str, order: int) -> float:
        book = ex.orderBook(symbol, limit=5)
        target = book['bids'] if dir in (kBuy, 'buy') else book['asks']
        return target[order][0]

    # 更新本地数据
    def _localCoin(self, exName:str, isPm:bool, coin:str = ''):
        trageEx = {}
        for k,v in self._localFree.items():
            for ex,it in v.items():
                if ex == exName:
                    trageEx = it
                    break
        key = isPm == True and kPm or 'free'
        if coin == '':
            return trageEx.setdefault(key, {})
        return trageEx.setdefault(key, {}).get(coin, 0)

    def _cleanBalanceData(self, data: dict) -> dict:
        clean = {}
        for key in ('free', 'total', kPm):
            value = data.get(key)
            if isinstance(value, dict):
                clean[key] = value
        return clean

    def _mergeBalance(self, target: dict, data: dict) -> None:
        for key, value in data.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                target[key].update(value)
            else:
                target[key] = value

    def _centerCoin(self, exName: str, isPm: bool, coin: str = '') -> float | dict:
        snapshot = evtFire(kEvt_Market, eMarketId['gBalance']) or {}
        target = {}
        for _, accounts in snapshot.items():
            for accountName, data in accounts.items():
                if accountName == exName:
                    target = data
                    break
        key = kPm if isPm else 'free'
        if coin == '':
            return target.get(key, {})
        return target.get(key, {}).get(coin, 0)

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

        if data.get('type') == kCancel:
            return True

        # 获取币种信息
        if symbolInfo is None and ex:
            _, symbolInfo = ex.coinInfo(symbol)
            data['coinInfo'] = symbolInfo

        step = symbolInfo.get('step') if symbolInfo else None
        priceMin = symbolInfo.get('price', {}).get('min') if symbolInfo else None
        amountMin = symbolInfo.get('amount', {}).get('min') if symbolInfo else None
        if orderPrice is not None and priceMin is not None:
            orderPrice = float(orderPrice)
            priceMin = float(priceMin)
            if orderPrice < priceMin:
                orderPrice = priceMin
            data['price'] = orderPrice

        # 平仓合约: 先找到持仓方向, 后续 BBO 才能按真实买/卖方向取价
        if direction == kClose:
            positions = data.get('_positions')
            if positions is None:
                querySymbol = symbolInfo.get('id') if symbolInfo else symbol
                positions = evtFire(kEvt_Market, eMarketId['gPosit'], 'ex', querySymbol)
                if not positions or exName not in positions:
                    return f"未找到持仓: {symbol} @ {exName}"
                positions = positions[exName]
                data['_positions'] = positions
            target = data.get('posSide')
            pos = positions[0] if positions else {}
            for item in positions:
                if target in ('all', '', None) or item.get('side') == target:
                    pos = item
                    break
            if pos.get('side') == kLong:
                data['_orderLookupDir'] = kSell
            elif pos.get('side') == kShort:
                data['_orderLookupDir'] = kBuy

        # 卖出现货 (绕过 preTrade, 需自行处理 consumeCoin/bet)
        if direction == kSell and not isPm:
            if consumeCoin is None:
                _, newSymbol = slit(symbol, '_')
                consumeCoin = newSymbol.split('/')[0] if '/' in newSymbol else ''
                data['consumeCoin'] = consumeCoin

            localCoin = self._centerCoin(exName, False, consumeCoin)
            if amountMin is not None and localCoin < float(amountMin):
                return f"卖出余额低于最小下单量: {consumeCoin}余额 {localCoin}, 最小 {amountMin}"

            # bet 转换: 卖出 bet:100 → 100% 持仓量
            if isinstance(totelPrice, str) and totelPrice.startswith('bet:'):
                proportion = float(totelPrice[4:]) * 0.01
                amount = self._floorAmount(proportion * localCoin, step)
                if amountMin is not None and amount < float(amountMin):
                    return f"卖出数量低于最小下单量: 当前 {amount}, 最小 {amountMin}"
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
            orderPrice = self._BBO(ex, symbol, data.get('_orderLookupDir', direction), orderBook)
            data['price'] = orderPrice

        # 计算数量
        if amount is None and orderPrice and direction != kClose:
            amount = division(totelPrice, orderPrice, step)
            data['amount'] = amount
        if amount and orderPrice and direction != kClose:
            data['totelPrice'] = orderPrice * amount

        # 校验取值范围
        if symbolInfo:
            if amount and not inRange([symbolInfo['amount'].get('min'), symbolInfo['amount'].get('max')], amount):
                return f"amount 取值范围: {symbolInfo['amount']}, 当前: {amount}"
            if orderPrice and not inRange([symbolInfo['price'].get('min'), symbolInfo['price'].get('max')], orderPrice):
                return f"price 取值范围: {symbolInfo['price']}, 当前: {orderPrice}"

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
        data.pop('_orderLookupDir', None)
        if positions:
            target = data.get('posSide')
            pos = positions[0]
            for item in positions:
                if target in ('all', '', None) or item.get('side') == target:
                    pos = item
                    break
            posSide = pos.get('side', '')
            if posSide == kLong:
                data['posSide'] = kLong
                data['orderDir'] = kSell
            elif posSide == kShort:
                data['posSide'] = kShort
                data['orderDir'] = kBuy
            data['amount'] = float(pos.get('amount', data.get('amount', 0)))

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

    def _floorAmount(self, amount: float, step: float | int | None) -> float:
        if not step:
            return amount
        stepDec = Decimal(str(step))
        if stepDec <= 0:
            return amount
        amountDec = Decimal(str(amount))
        return float((amountDec / stepDec).to_integral_value(rounding=ROUND_DOWN) * stepDec)
