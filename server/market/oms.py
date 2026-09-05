import copy
from decimal import Decimal, ROUND_DOWN
from typing import Any, Callable
from server.utils import evtConnect, evtFireAsync, kEvt_Market, log, switchFn, evtReturn, slit, division,inRange,warn,generateId,threadCall,spawnTask
from server.market import eMarketId, kSwap, kBuy, kSell,kPm,kClose,kCancel,kLong,kShort
from server.market.baseExchange import baseExchange

class oms:
    "本地订单管理：算价/算量/本地余额校验与扣减。由 gateway 流水线直接调用,只在总线上监听余额更新"

    def __init__(self, exFn: Callable[[str], baseExchange | None] | None = None):
        self._localFree: dict[str, dict[str, dict]] = evtReturn(kEvt_Market, 'storageCenter', eMarketId['gBalance']) or {}  # 本地缓存的 center 数据: {exId: {account: {...}}}
        self._getEx = exFn                  # exName → baseExchange
        # self._clientOrderSeq: int = 0       # 自增序号,配合 time2ID 保证并发下单时 clientOrderId 不撞车
        self._checkingOrders: bool = False  # 防止上次定时检查未结束时重复处理同一批挂单
        evtConnect(kEvt_Market, self)

    def evtProcess(self, key: object, *args: Any) -> None:
        id_ = args[0]
        def _balanceUpdate() -> None:
            exId = args[1] if len(args) > 1 else ''
            account = args[2] if len(args) > 2 else ''
            data = args[3] if len(args) > 3 else {}
            if not (exId and account and isinstance(data, dict)):
                return
            target = self._localFree.setdefault(exId, {}).setdefault(account, {})
            cleanData = self._cleanBalanceData(data)
            if not cleanData:
                return
            self._mergeBalance(target, cleanData)
            if id_ == eMarketId['balance']:
                self._logLocalFree(exId, account, target)

        def _kickOffCheckOrders() -> None:
            if self._checkingOrders:
                return
            self._checkingOrders = True
            spawnTask(self._checkOrders(), name="oms:checkOrders")

        switchFn({eMarketId['balance']: _balanceUpdate,
                  eMarketId['wsBalance']: _balanceUpdate,
                  eMarketId['checkOrders']: _kickOffCheckOrders}, key=id_)

    #订单检查(是否成交)
    async def _checkOrders(self) -> None:
        try:
            records: list[dict] = evtReturn(kEvt_Market, 'storageOrders', eMarketId['gOpenOrders']) or []
            if not records:
                return
            for record in records:
                try:
                    await self._checkOpenOrder(record)
                except Exception as e:
                    warn(f"[oms] 订单追踪失败 {record.get('symbol', '')}/"
                         f"{record.get('orderID', '')}: {e}")
        finally:
            self._checkingOrders = False
    async def _checkOpenOrder(self, record: dict) -> None:
        orderID: str = str(record.get('orderID') or '')
        exName: str = record.get('exName', '')
        symbol: str = record.get('symbol', '')
        ex = self._getEx(exName) if self._getEx else None
        if not ex or not orderID or not symbol:
            return

        orders = await threadCall(ex, ex.findOrder, symbol, orderID, isPos=False, isOpen=True)
        order = self._findOpenOrder(orders, orderID)
        if not order:
            return

        retry = int(record.get('retry') or 0) + 1
        update = {'exName': exName, 'taskName': record.get('taskName'),
                  'orderID': orderID, 'retry': retry}
        evtFireAsync(kEvt_Market, eMarketId['uOpenOrder'], update)
        if retry > 3:
            await self._replaceOpenOrder(ex, record)
            return

        book = await threadCall(ex, ex.orderBook, symbol, limit=5) or {}
        direction = record.get('dir')
        side = book.get('asks' if direction == kBuy else 'bids', [])
        if not side:
            return
        newPrice = float(side[0][0])
        remaining = self._orderRemaining(order, record)
        amount = self._orderAmount(record, newPrice, remaining, ex)
        if amount <= 0:
            return
        result = await threadCall(ex, ex.editOrder, orderID, symbol, direction, amount, newPrice)
        if not result:
            raise RuntimeError('改单未返回订单数据')
        update.update(price=newPrice, amount=amount)
        evtFireAsync(kEvt_Market, eMarketId['uOpenOrder'], update)
        log(f"[oms] 修改挂单成功: {exName} {symbol} orderID={orderID} "
            f"price={newPrice} amount={amount} total={record.get('totelPrice')} "
            f"retry={retry}")
        
    async def _replaceOpenOrder(self, ex: baseExchange, record: dict) -> None:
        orderID: str = str(record.get('orderID') or '')
        symbol: str = record.get('symbol', '')
        cancelResult = await ex.order(kCancel, symbol, orderID, 0)
        if not cancelResult:
            raise RuntimeError(f'撤销原挂单失败: {orderID}')
        remaining = self._orderRemaining(cancelResult, record)
        if remaining <= 0:
            ex.requestBalanceRefresh()
            return

        replacement = copy.deepcopy(record)
        replacement.update(orderID='', clientOrderId='', amount=remaining,
                           retry=0, isMarket=True, price=None, orderBook=-1,
                           _replaceOrder=True)
        if replacement.get('dir') == kClose and not replacement.get('orderDir'):
            replacement['orderDir'] = (
                kSell if replacement.get('posSide') == kLong else kBuy)
        evtFireAsync(kEvt_Market, eMarketId['submit'], replacement)
        log(f"[oms] 挂单超过3次未成交,已撤单并提交市价替换: {symbol} " f"oldOrderID={orderID} amount={remaining}")

    def _findOpenOrder(self, orders: list | tuple | dict | None, orderID: str) -> dict | None:
        # exchange.findOrder() 现货返回 list,合约返回 (open_orders, pos_orders) 元组,这里统一拍平成 list 处理
        if isinstance(orders, tuple):
            orders = orders[0]
        if isinstance(orders, dict):
            orders = [orders]
        if not isinstance(orders, list):
            return None
        for order in orders:
            info = order.get('info') or {}
            currentID = order.get('id') or order.get('orderId') or info.get('orderId')
            if str(currentID or '') == orderID:
                return order
        return None

    def _orderRemaining(self, order: dict, record: dict) -> float:
        remaining = order.get('remaining')
        try:
            if remaining is not None:
                return max(float(remaining), 0.0)
        except (TypeError, ValueError):
            pass
        info = order.get('info') or order
        try:
            amount = float(order.get('amount') or info.get('origQty') or info.get('q') or 0)
            filled = float(order.get('filled') or info.get('executedQty') or info.get('z') or 0)
            if amount > 0:
                return max(amount - filled, 0.0)
        except (TypeError, ValueError):
            pass
        return float(record.get('amount') or 0.0)

    def _orderAmount(self, record: dict, price: float, remaining: float, ex: baseExchange) -> float:
        total = float(record.get('totelPrice') or 0.0)
        oldPrice = float(record.get('price') or 0.0)
        target = total / price if total > 0 else remaining
        if oldPrice > 0 and remaining < float(record.get('amount') or remaining):
            target = remaining * oldPrice / price
        _, info = ex.coinInfo(record.get('symbol', ''))
        step = info.get('step') if info else None
        return self._floorAmount(target, step)

    # ── gateway 流水线入口: 校验+算价算量+扣本地余额。通过返回True,拦截返回原因字符串 ──
    async def prepare(self, data: dict) -> bool | str:
        orderType = data.get('type', '')
        direction = data.get('dir', '')
        isPm = orderType == kSwap

        # 1. 校验 + 准备参数 (价格/数量)
        result = await self._checkOrder(data, isPm)
        if result is not True:
            return result
        if orderType == kCancel:
            return True

        if data.get('_replaceOrder'):
            self._ensureClientOrderId(data)
            return True

        # 2. 余额处理
        if direction == kClose or (direction == kSell and not isPm):
            self._close(data)
        else:
            # 买入/开仓: 扣减 consumeCoin 余额
            fixTotel = (data.get('price') or 0) * (data.get('amount') or 0) or data.get('totelPrice', 0)
            if isPm:
                key, consumeCoin = kPm, 'free'
                money = self._localCoin(data.get('exName'), isPm).get(consumeCoin, 0) * 0.9
            else:
                key, consumeCoin = 'total', data.get('consumeCoin', 'USDT')
                money = self._localCoin(data.get('exName'), isPm, key=key).get(consumeCoin, 0)
            if money < fixTotel:
                return f"下单金额不足: {fixTotel}, 可用: {money}"
            self._deduct(data, key, consumeCoin, fixTotel)

        # 3. 生成幂等id,供WS回报匹配
        self._ensureClientOrderId(data)
        return True

    # 幂等id缺失时补一个,prepare() 内两处会用到
    def _ensureClientOrderId(self, data: dict) -> None:
        if not data.get('clientOrderId'):
            data['clientOrderId'] = generateId()#self._genClientOrderId()

    # 扣减本地余额并记录,供下单失败时 rollback
    def _deduct(self, data: dict, key: str, coin: str, amount: float) -> None:
        localData = self._localCoin(data.get('exName'), False, key=key)
        localData[coin] = localData.get(coin, 0) - amount
        data['_deduct'] = {'key': key, 'coin': coin, 'amount': amount}

    # 下单失败: 把 prepare 阶段的本地扣减加回去,避免本地余额单向漂移
    def rollback(self, data: dict) -> None:
        rec = data.pop('_deduct', None)
        if not rec:
            return
        localData = self._localCoin(data.get('exName'), False, key=rec['key'])
        localData[rec['coin']] = localData.get(rec['coin'], 0) + rec['amount']
        log(f"[oms] 下单失败,回滚本地扣减: {rec['key']}/{rec['coin']} +{rec['amount']}")

    # ── 当前挂单最优价 ──
    async def _BBO(self, ex: baseExchange, symbol: str, direction: str, order: int, aggressive: bool = False) -> float:
        book = await threadCall(ex, ex.orderBook, symbol, limit=max(10, order + 4))
        isBuy = direction == kBuy
        target = (book['asks'] if isBuy else book['bids']) if aggressive else (book['bids'] if isBuy else book['asks'])
        order = min(max(order, 0), len(target) - 1)
        return target[order][0]

    # 在 {exId: {account: {...}}} 快照里按 account 名找出对应字典
    def _findAccount(self, snapshot: dict, exName: str) -> dict:
        for accounts in snapshot.values():
            if exName in accounts:
                return accounts[exName]
        return {}

    # 更新本地数据; key 显式传入时会覆盖 isPm 推导出的默认桶('pm'/'free'),此时 isPm 本身不再生效
    def _localCoin(self, exName: str, isPm: bool, coin: str = '', key: str | None = None) -> float | dict:
        trageEx = self._findAccount(self._localFree, exName)
        key = key or (kPm if isPm else 'free')
        if coin == '':
            return trageEx.setdefault(key, {})
        return trageEx.setdefault(key, {}).get(coin, 0)

    def _cleanBalanceData(self, data: dict) -> dict:
        if data.get('info', {}).get('fs') in ('UM', 'CM'):
            return {}
        clean = {}
        for key in ('free', 'total', kPm):
            value = data.get(key)
            if isinstance(value, dict):
                clean[key] = value
        return clean

    def _mergeBalance(self, target: dict, data: dict) -> None:
        for key, value in data.items():
            value = copy.deepcopy(value)
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                target[key].update(value)
            else:
                target[key] = value

    def _logLocalFree(self, exId: str, account: str, data: dict) -> None:
        pmData = data.get(kPm, {}) if isinstance(data, dict) else {}
        log("[oms.balance] _localFree REST更新:",
            {'exId': exId, 'account': account, 'free': pmData.get('free'),
             'equity': pmData.get('equity'), 'USDT': pmData.get('total', {}).get('USDT')})

    def _centerCoin(self, exName: str, isPm: bool, coin: str = '') -> float | dict:
        snapshot = evtReturn(kEvt_Market, 'storageCenter', eMarketId['gBalance']) or {}
        target = self._findAccount(snapshot, exName)
        key = kPm if isPm else 'free'
        if coin == '':
            return target.get(key, {})
        return target.get(key, {}).get(coin, 0)

    # ── 校验订单 + 准备价格/数量 ──
    async def _checkOrder(self, data: dict, isPm: bool) -> bool | str:
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
                positions = evtReturn(kEvt_Market, 'storageOrders', eMarketId['gPosit'],
                                      'ex', querySymbol, exName, data.get('taskName', ''))
                if not positions or exName not in positions:
                    return f"未找到持仓: {symbol} @ {exName}"
                positions = positions[exName]
                data['_positions'] = positions
            target = data.get('posSide')
            pos = self._targetPosition(positions, target)
            if not pos:
                return f"未找到持仓方向: {symbol} {target}"
            data['_positions'] = [pos]
            if pos.get('side') == kLong:
                data['_orderLookupDir'] = kSell
            elif pos.get('side') == kShort:
                data['_orderLookupDir'] = kBuy

        # 卖出现货 (绕过 preTrade, 需自行处理 consumeCoin/bet)
        if direction == kSell and not isPm:
            if consumeCoin is None:
                splitSymbol = slit(symbol, '_')
                newSymbol = splitSymbol[1] if splitSymbol else symbol
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
                    orderPrice = await self._BBO(ex, symbol, direction, orderBook, not data.get('isMarket', False))
                    data['price'] = orderPrice
                if orderPrice:
                    data['totelPrice'] = orderPrice * amount

            if amount and localCoin < amount:
                return f"卖出余额不足: 需要 {amount}, 持有 {localCoin}"

        # 获取 BBO 价格 (非卖出已处理的情况)
        if orderPrice is None and orderBook >= 0 and ex:
            orderPrice = await self._BBO(ex, symbol, data.get('_orderLookupDir', direction), orderBook,
                                         not data.get('isMarket', False))
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
    def _close(self, data: dict) -> None:
        direction = data.get('dir', '')
        isPm = data.get('type', '') == kSwap
        # 卖现货: 扣减币余额
        if direction == kSell and not isPm:
            consumeCoin = data.get('consumeCoin', '')
            self._deduct(data, 'free', consumeCoin, data.get('amount', 0))
            return
        # elif direction == kClose:
        # 平仓合约: 从持仓数据设置反向
        positions = data.pop('_positions', [])
        data.pop('_orderLookupDir', None)
        if positions:
            target = data.get('posSide')
            pos = self._targetPosition(positions, target)
            if not pos:
                warn(f"未找到可平仓方向: {data.get('symbol', '')} {target}")
                return
            posSide = pos.get('side', '')
            if posSide == kLong:
                data['posSide'] = kLong
                data['orderDir'] = kSell
            elif posSide == kShort:
                data['posSide'] = kShort
                data['orderDir'] = kBuy
            data['amount'] = float(pos.get('amount', data.get('amount', 0)))
            data['_positionOrderIDs'] = pos.get('orderIDs') or [pos.get('orderID', '')]

    def _targetPosition(self, positions: list[dict], target: str | None) -> dict:
        if not positions:
            return {}
        if target in ('all', '', None):
            return positions[0]
        for item in positions:
            if item.get('side') == target:
                return item
        return {}

    # def _genClientOrderId(self) -> str:
        # self._clientOrderSeq += 1
        # return f"{time2Id()}{self._clientOrderSeq}"

    def _floorAmount(self, amount: float, step: float | int | None) -> float:
        if not step:
            return amount
        stepDec = Decimal(str(step))
        if stepDec <= 0:
            return amount
        amountDec = Decimal(str(amount))
        return float((amountDec / stepDec).to_integral_value(rounding=ROUND_DOWN) * stepDec)