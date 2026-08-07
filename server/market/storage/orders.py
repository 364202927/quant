from datetime import datetime, timezone
from typing import Callable
from server.utils import evtConnect, kEvt_Market, switchFn, recordBuffer,log
from server.market import eMarketId, kSpot, kSwap, kBuy, kSell, kClose, kLong, kShort, kCancel

class storageOrders:
    "订单/状态事件监听 数据保存整理 "

    def __init__(self):
        self.__taskOrders: dict[str, list[dict]] = {}  # task正持有的订单
        self.__taskHistory = recordBuffer()     # 任务历史订单
        self.__openOrders = {}                  #task开仓记录
        #todo:读取__taskOrders保存的文件
        evtConnect(kEvt_Market, self)

    def evtProcess(self, key, *args):
        # len(args) > 2 而非 > 1: 用来区分"只带一个 payload"的事件(如 order/gPosit, args[1] 是 dict/查询参数)
        # 和"携带 exName"的事件(wsOrder, args 至少有 marketId+exName+其它)
        marketId, exName = args[0], args[1] if len(args) > 2 else None
        #返回持仓
        def _gPosit():
            queryType = args[1] if len(args) > 1 else ''
            symbol = args[2] if len(args) > 2 else ''
            account = args[3] if len(args) > 3 else ''
            # queryType: 'task'从运行任务中找 / 'ex'从交易所中寻找
            if queryType == 'task':
                result = self._taskPositions(symbol, account)
                return result or None
            # 'ex': OMS 需要按交易所账号返回, 但仓位来源使用 task 当前持仓.
            result = self._taskExchangePositions(symbol, account)
            return result or None

        # 记录oms通过的订单
        def _saveOrder():
            data = args[1] if len(args) > 1 else {}
            orderType = data.get('type', '')
            if orderType == kCancel:
                log(f"[storageOrders] 撤单发送: {data.get('exName', '')} {data.get('symbol', '')} {data.get('orderID', '')}")
                return
            symbol = data.get('symbol', '')
            direction = data.get('dir', '')
            taskName = self._taskName(data.get('taskName'))
            if taskName == 'other':
                return
            coinInfo = data.get("coinInfo") or {}
            coinId = coinInfo.get('id') or self._cleanSymbol(symbol)
            exName = data.get('exName', '')
            record = {
                'symbol': symbol,
                'orderID': data.get('orderID', ''),
                'clientOrderId': data.get('clientOrderId', ''),
                'dir': direction,
                'type': orderType,
                'posSide': data.get('posSide'),
                'price': data.get('price'),
                'amount': data.get('amount'),
                'totelPrice': data.get('totelPrice', 0),
                'taskName': taskName,
            }
            self.__openOrders.setdefault(exName, {}).setdefault(taskName, {}).setdefault(coinId, []).append(record)
            # log("~~~~oms_saveOrder~~~~",self.__openOrders)

        # ws订单数据更新
        def _wsUpdateOrder():
            order = args[2] if len(args) > 2 else {}
            info = order.get('info', {})
            if not info:
                return
            status = order.get('status')
            # log("~~~~~~_wsUpdateOrder~~~~~~~",self.__openOrders)
            # print("~~~~~~__openOrders~~~~~~~",self.__openOrders)
            coinId = info.get('s', '')
            wsPs = info.get('ps', None)           # 持仓方向: LONG/SHORT/None(现货)
            wsSide = order.get('side', '')        # 'buy' / 'sell'
            isReduce = order.get('reduceOnly', False) or self._bool(info.get('R')) or self._bool(info.get('reduceOnly'))
            
            # 确定 WS 对应的 dir (kBuy/kSell/kClose)
            if isReduce and wsPs is not None:
                wsDir = kClose
            else:
                wsDir = kBuy if wsSide == 'buy' else kSell
            # log("~~~~~~_wsUpdateOrder~~~~~~~",wsDir,exName,coinId)
            # exName 即交易所 classId, 直接定位 __openOrders

            matched, matchedTask = self._popTempOrder(exName, coinId, order, wsDir, wsPs)

            if matched is None:
                if wsDir == kClose and order.get('status') == 'closed':
                    matched, matchedTask = self._matchManualCloseOrder(order, wsPs)
            if matched is None:
                matched = self._wsRecord(order, wsDir)
                matchedTask = matched['taskName']
            if matchedTask == 'other':
                return
            if status == 'canceled':
                # log("~~~~~~cancel tempData~~~~~",matched)
                # log("~~~~__openOrders~~~~~",self.__openOrders)
                return

            # 订单时间: 使用 WS 返回的 timestamp, 格式与 str2time('strNow') 一致
            wsTs = order.get('timestamp', 0)
            orderTime = self._orderTime(wsTs)

            # 合并 WS 数据
            fullRecord = {
                'time': orderTime,
                'tags': [exName, matchedTask, coinId],
                'symbol': matched.get('symbol'),
                'orderID': order.get('id', ''),
                'dir': self._recordDir(order),
                'price': order.get('average'),                  # 成交均价 (=开仓价 或 平仓价)
                'total': order.get('cost', 0),                  # 总金额
                'amt': order.get('filled', 0),                  # 已成交数量
                'fee': self._fee(order),                        # 手续费 (币种:数量)
                'profit': self._profit(info),                   # 已实现盈亏
            }

            if matched['type'] == kSpot:
                self.__taskHistory.push(**fullRecord)
                # print(f"[storageOrders] 现货→历史: {coinId} {wsSide}")
                # log("~~~~~~find tempData~~~~~",matched)
                # log("~~~~~~saveRec~~~~~~~~",fullRecord)
                # log("~~~~__openOrders~~~~~",self.__openOrders)
                # log("~~~~__taskOrders~~~~~",self.__taskOrders)
                log("~~~~__taskHistory~~~~~",self.__taskHistory.buffer())
                return
            else:
                if matched.get('dir') == kClose:
                    fullRecord['dir'] = kClose
                self._updateTaskOrders(matchedTask, matched, fullRecord)
                self.__taskHistory.push(**fullRecord)
                log("~~~~__taskHistory~~~~~",self.__taskHistory.buffer())
                # print(f"[storageOrders] 合约→活跃+历史: {coinId} {wsSide}")
            # log("~~~~~~find tempData~~~~~",matched)
            # log("~~~~~~saveRec~~~~~~~~",fullRecord)
            # log("~~~~__openOrders~~~~~",self.__openOrders)
            # log("~~~~__taskOrders~~~~~",self.__taskOrders)
            # log("~~~~__taskHistory~~~~~",self.__taskHistory.buffer())
            

        result = switchFn({eMarketId['order']: _saveOrder,
                         # eMarketId['orderCache']: _saveOrder,
                           eMarketId['wsOrder']: _wsUpdateOrder,
                           eMarketId['gPosit']: _gPosit,
                         }, key=marketId)
        return None if result is False else result

    def _cleanSymbol(self, symbol: str) -> str:
        if not symbol:
            return ''
        clean = symbol.split('_')[-1]
        clean = clean.split(':')[0]
        return clean.replace('/', '').replace('-', '')

    def _taskPositions(self, symbol: str, taskName: str = '') -> dict:
        result = {}
        querySymbol = self._cleanSymbol(symbol)
        for task, orders in self.__taskOrders.items():
            if taskName and task != taskName:
                continue
            for order in orders:
                orderSymbol = self._cleanSymbol(order.get('symbol', ''))
                if querySymbol and querySymbol not in orderSymbol:
                    continue
                result.setdefault(task, []).append(order)
        return result

    def _taskExchangePositions(self, symbol: str, account: str = '') -> dict:
        positions = []
        querySymbol = self._cleanSymbol(symbol)
        for orders in self.__taskOrders.values():
            for order in orders:
                orderSymbol = self._cleanSymbol(order.get('symbol', ''))
                if querySymbol and querySymbol not in orderSymbol:
                    continue
                side = self._taskOrderSide(order)
                if not side:
                    continue
                amount = self._taskOrderAmount(order)
                if amount <= 0:
                    continue
                positions.append({
                    'symbol': self._cleanSymbol(order.get('symbol', '')),
                    'dir': f"{side == kLong and kBuy or kSell}_{side}",
                    'side': side,
                    'open': order.get('price'),
                    'unRealized': 0,
                    'amount': amount,
                })
        if not positions:
            return {}
        return {account: positions} if account else {'task': positions}

    def _updateTaskOrders(self, taskName: str, matched: dict, record: dict) -> None:
        direction = self._taskOrderDir(matched, record)
        if not direction:
            return
        if record.get('dir') == kClose:
            self._removeTaskOrder(taskName, matched.get('symbol', ''), direction)
            return
        self._upsertTaskOrder(taskName, {
            'orderID': record.get('orderID', ''),
            'symbol': matched.get('symbol', ''),
            'dir': direction,
            'price': record.get('price'),
        })

    def _taskOrderDir(self, matched: dict, record: dict) -> str:
        posSide = matched.get('posSide')
        recordDir = record.get('dir', '')
        if posSide == kLong or recordDir.endswith(kLong):
            return 'long'
        if posSide == kShort or recordDir.endswith(kShort):
            return 'short'
        return ''

    def _taskOrderSide(self, order: dict) -> str:
        direction = order.get('dir', '')
        if direction == 'long':
            return kLong
        if direction == 'short':
            return kShort
        return ''

    def _taskOrderAmount(self, order: dict) -> float:
        orderId = str(order.get('orderID') or '')
        if not orderId:
            return self._float(order.get('amount'))
        for record in reversed(self.__taskHistory.buffer()):
            data = record.get('data', {})
            if str(data.get('orderID') or '') != orderId:
                continue
            return self._float(data.get('amt'))
        return self._float(order.get('amount'))

    def _upsertTaskOrder(self, taskName: str, order: dict) -> None:
        orders = self.__taskOrders.setdefault(taskName, [])
        symbol = self._cleanSymbol(order.get('symbol', ''))
        direction = order.get('dir', '')
        for index, item in enumerate(orders):
            if self._cleanSymbol(item.get('symbol', '')) == symbol and item.get('dir') == direction:
                orders[index] = order
                return
        orders.append(order)

    def _removeTaskOrder(self, taskName: str, symbol: str, direction: str) -> None:
        orders = self.__taskOrders.get(taskName, [])
        cleanSymbol = self._cleanSymbol(symbol)
        self.__taskOrders[taskName] = [
            order for order in orders
            if self._cleanSymbol(order.get('symbol', '')) != cleanSymbol or order.get('dir') != direction
        ]
        if not self.__taskOrders[taskName]:
            del self.__taskOrders[taskName]

    def _taskName(self, taskName: str | None) -> str:
        return taskName or 'other'

    def _wsRecord(self, order: dict, wsDir: str) -> dict:
        return {
            'symbol': order.get('symbol', ''),
            'orderID': order.get('id', ''),
            'clientOrderId': order.get('clientOrderId', ''),
            'dir': wsDir,
            'type': kSwap if order.get('reduceOnly') or order.get('info', {}).get('ps') else kSpot,
            'posSide': order.get('info', {}).get('ps'),
            'price': order.get('average') or order.get('price'),
            'amount': order.get('amount') or order.get('filled'),
            'totelPrice': order.get('cost', 0),
            'taskName': 'other',
        }

    def _orderTime(self, timestamp: int | float | None) -> str:
        if timestamp:
            return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    def _recordDir(self, order: dict) -> str:
        info = order.get('info', {})
        side = order.get('side', '')
        posSide = info.get('ps') or order.get('positionSide')
        reduceOnly = order.get('reduceOnly') or self._bool(info.get('R')) or self._bool(info.get('reduceOnly'))
        if reduceOnly or info.get('x') == 'CALCULATED':
            return kClose
        if posSide:
            return f"{side}_{posSide}"
        return side

    def _bool(self, value: object) -> bool:
        if isinstance(value, str):
            return value.lower() == 'true'
        return bool(value)

    def _float(self, value: object) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    def _profit(self, info: dict) -> float:
        profit = info.get('rp')
        if profit is None:
            return 0.0
        try:
            return float(profit)
        except (TypeError, ValueError):
            return 0.0

    def _popTempOrder(self, exName: str, coinId: str, order: dict, wsDir: str, wsPs: str | None) -> tuple[dict | None, str]:
        orderId = str(order.get('id') or '')
        clientOrderId = str(order.get('clientOrderId') or order.get('info', {}).get('c') or '')
        matched = self._popTempOrderBy(
            exName,
            coinId,
            lambda rec: self._sameOrderId(rec, orderId, clientOrderId),
        )
        if matched[0] is not None:
            return matched
        matched = self._popTempOrderBy(
            exName,
            coinId,
            lambda rec: self._sameOrderSide(rec, wsDir, wsPs) and self._sameOrderTradeData(rec, order),
        )
        if matched[0] is not None:
            return matched
        return self._popTempOrderBy(
            exName,
            coinId,
            lambda rec: self._sameOrderSide(rec, wsDir, wsPs),
        )

    def _popTempOrderBy(self, exName: str, coinId: str, matchFn: Callable[[dict], bool]) -> tuple[dict | None, str]:
        exOrders = self.__openOrders.get(exName, {})
        for taskName, taskOrders in list(exOrders.items()):
            tempData = taskOrders.get(coinId)
            if not tempData:
                continue
            for i, rec in enumerate(tempData):
                if not matchFn(rec):
                    continue
                matched = tempData.pop(i)
                if not tempData:
                    del taskOrders[coinId]
                if not taskOrders:
                    del exOrders[taskName]
                if not exOrders:
                    del self.__openOrders[exName]
                return matched, taskName
        return None, ''

    def _matchManualCloseOrder(self, order: dict, posSide: str | None) -> tuple[dict | None, str]:
        direction = self._posDirection(posSide)
        if not direction:
            return None, ''
        cleanSymbol = self._cleanSymbol(order.get('symbol', ''))
        for taskName, taskOrders in self.__taskOrders.items():
            for rec in taskOrders:
                if self._cleanSymbol(rec.get('symbol', '')) != cleanSymbol:
                    continue
                if rec.get('dir') != direction:
                    continue
                matched = {
                    'symbol': rec.get('symbol', order.get('symbol', '')),
                    'orderID': order.get('id', ''),
                    'clientOrderId': order.get('clientOrderId', ''),
                    'dir': kClose,
                    'type': kSwap,
                    'posSide': posSide,
                    'price': order.get('average') or order.get('price'),
                    'amount': order.get('filled') or order.get('amount'),
                    'totelPrice': order.get('cost', 0),
                    'taskName': taskName,
                }
                return matched, taskName
        return None, ''

    def _posDirection(self, posSide: str | None) -> str:
        if posSide == kLong:
            return 'long'
        if posSide == kShort:
            return 'short'
        return ''

    def _sameOrderId(self, rec: dict, orderId: str, clientOrderId: str) -> bool:
        recOrderId = str(rec.get('orderID') or '')
        recClientOrderId = str(rec.get('clientOrderId') or '')
        if orderId and recOrderId == orderId:
            return True
        return bool(clientOrderId and recClientOrderId == clientOrderId)

    def _sameOrderSide(self, rec: dict, wsDir: str, wsPs: str | None) -> bool:
        recDir = rec.get('dir', '')
        recPos = rec.get('posSide')
        if recDir == kClose:
            return bool(wsPs and wsPs == recPos)
        if recDir != wsDir:
            return False
        if wsDir == kClose:
            return wsPs == recPos
        if wsPs is not None:
            return recPos == wsPs
        return True

    def _sameOrderTradeData(self, rec: dict, order: dict) -> bool:
        price = order.get('price') or order.get('average')
        amount = order.get('amount') or order.get('filled')
        return self._sameNumber(rec.get('price'), price) and self._sameNumber(rec.get('amount'), amount)

    def _sameNumber(self, left, right) -> bool:
        if left is None or right is None:
            return False
        try:
            return abs(float(left) - float(right)) < 1e-12
        except (TypeError, ValueError):
            return False

    def _fee(self, order: dict) -> dict:
        info = order.get('info', {})
        if info.get('N'):
            return {info.get('N'): info.get('n')}
        fee = order.get('fee') or {}
        if fee.get('currency'):
            return {fee.get('currency'): fee.get('cost')}
        fees = order.get('fees') or []
        result = {}
        for item in fees:
            if item.get('currency'):
                result[item.get('currency')] = item.get('cost')
        return result
