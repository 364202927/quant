import copy
import os
from datetime import datetime, timezone
from typing import Callable, Iterable
from server.utils import evtConnect, kEvt_Market, switchFn, recordBuffer,log, warn, readFile, writeFile, debouncedSaver
from server.utils.fileConfig import kOtherPath
from server.market import (eMarketId, kSpot, kSwap, kBuy, kSell, kClose,kLong, kShort, kCancel, kOrderFailedStatuses)

kOrdersStateFile = kOtherPath + 'orders.json'
kHistoryDir = kOtherPath + 'history/'

class storageOrders:
    "订单/状态事件监听 数据保存整理 "

    def __init__(self):
        state = readFile(kOrdersStateFile) or {}
        self.__taskOrders: dict[str, list[dict]] = state.get('taskOrders', {})  # task正持有的订单
        self.__openOrders = state.get('openOrders', {})                        #task开仓记录
        self.__taskHistory = recordBuffer(kHistoryDir, max_size=1024)          # 任务历史订单
        self.__historyLoaded = False                                           # 读取时才全量加载
        self._requestSave = debouncedSaver(2.0, self._saveState)
        evtConnect(kEvt_Market, self)

    # 停机时调用: 跳过防抖,强制落盘一次
    def flush(self) -> None:
        self._saveState()

    def _saveState(self) -> None:
        if not self.__taskOrders and not self.__openOrders:
            if os.path.isfile(kOrdersStateFile):
                os.remove(kOrdersStateFile)
        else:
            writeFile({'taskOrders': self.__taskOrders, 'openOrders': self.__openOrders}, kOrdersStateFile)
        self.__taskHistory.save2File()

    # 历史订单只在真正需要读取时才全量加载(而非启动时预加载最近N天)
    def _history(self) -> list[dict]:
        if not self.__historyLoaded:
            self.__taskHistory.readFile(days=None)
            self.__historyLoaded = True
        return self.__taskHistory.buffer()

    def evtProcess(self, key, *args):
        # len(args) > 2 而非 > 1: 用来区分"只带一个 payload"的事件(如 order/gPosit, args[1] 是 dict/查询参数)
        # 和"携带 exName"的事件(wsOrder, args 至少有 marketId+exName+其它)
        marketId, exName = args[0], args[1] if len(args) > 2 else None
        #返回持仓
        def _gPosit():
            queryType = args[1] if len(args) > 1 else ''
            symbol = args[2] if len(args) > 2 else ''
            account = args[3] if len(args) > 3 else ''
            taskName = args[4] if len(args) > 4 else ''
            # queryType: 'task'从运行任务中找 / 'ex'从交易所中寻找
            if queryType == 'task':
                result = self._taskPositions(symbol, account)
                return result or None
            # 'ex': OMS 需要按交易所账号返回, 但仓位来源使用 task 当前持仓.
            result = self._taskExchangePositions(symbol, account, taskName)
            return result or None

        def _gOpenOrders():
            result = []
            for currentEx, tasks in self.__openOrders.items():
                for currentTask, coins in tasks.items():
                    for records in coins.values():
                        for record in records:
                            item = copy.deepcopy(record)
                            item['exName'] = currentEx
                            item['taskName'] = currentTask
                            result.append(item)
            return result or None

        def _uOpenOrder():
            data = args[1] if len(args) > 1 else {}
            orderID = str(data.get('orderID') or '')
            if not orderID:
                return
            exName = data.get('exName', '')
            taskName = self._taskName(data.get('taskName'))
            taskOrders = self.__openOrders.get(exName, {}).get(taskName, {})
            for records in taskOrders.values():
                for record in records:
                    if str(record.get('orderID') or '') != orderID:
                        continue
                    for key in ('price', 'amount', 'retry'):
                        if key in data:
                            record[key] = data[key]
                    self._requestSave()
                    return

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
                'orderDir': data.get('orderDir'),
                'price': data.get('price'),
                'amount': data.get('amount'),
                'totelPrice': data.get('totelPrice', 0),
                'isMarket': data.get('isMarket', False),
                'inForce': data.get('inForce', 'GTC'),
                'lv': data.get('lv', 1),
                'taskName': taskName,
                'positionOrderIDs': data.get('_positionOrderIDs', []),
                'retry': data.get('retry', 0),
                'time': self._orderTime(None),
            }
            self._warnDuplicateOpen(exName, taskName, coinId, record)
            self.__openOrders.setdefault(exName, {}).setdefault(taskName, {}).setdefault(coinId, []).append(record)
            self._requestSave()

        # 下单失败: 删掉 _saveOrder 刚记的待匹配记录,否则它永远等不到WS回报变成孤儿
        def _failOrder():
            data = args[1] if len(args) > 1 else {}
            if data.get('type') == kCancel:
                return
            orderID = str(data.get('orderID') or '')
            clientOrderId = str(data.get('clientOrderId') or '')
            if not orderID and not clientOrderId:
                return
            coinInfo = data.get("coinInfo") or {}
            coinId = coinInfo.get('id') or self._cleanSymbol(data.get('symbol', ''))
            matched, _ = self._popTempOrderBy(
                data.get('exName', ''),
                lambda rec: self._sameOrderId(rec, orderID, clientOrderId))
            if matched:
                log(f"[storageOrders] 下单失败,移除待匹配记录: {coinId} clientOrderId={clientOrderId}")

        def _acceptOrder():
            data = args[1] if len(args) > 1 else {}
            self._bindOrderId(data)

        # 启动时用交易所真实持仓/挂单校验并矫正本地记录(依赖本地文件已在 __init__ 里加载完毕)
        def _verifyPositions():
            data = args[3] if len(args) > 3 else {}
            self._reconcilePositions(exName, data.get('pos') or [])
            self._reconcileOpenOrders(exName, data.get('open') or [])

        # ws订单数据更新
        def _wsUpdateOrder():
            order = args[2] if len(args) > 2 else {}
            info = order.get('info', {})
            if not info:
                return
            status = str(order.get('status') or '').lower()
            coinId = info.get('s', '')
            wsPs = info.get('ps', None)           # 持仓方向: LONG/SHORT/None(现货)
            wsSide = order.get('side', '')        # 'buy' / 'sell'
            isReduce = order.get('reduceOnly', False) or self._bool(info.get('R')) or self._bool(info.get('reduceOnly'))
            
            # 确定 WS 对应的 dir (kBuy/kSell/kClose)
            if isReduce and wsPs is not None:
                wsDir = kClose
            else:
                wsDir = kBuy if wsSide == 'buy' else kSell
            matched, matchedTask = self._popTempOrder(exName, order)

            if status in kOrderFailedStatuses:
                if matched is None:
                    log(f"[storageOrders] 失败订单未找到待匹配记录: {coinId} "
                        f"orderID={order.get('id', '')} clientOrderId={order.get('clientOrderId', '')}")
                if self._float(order.get('filled')) <= 0:
                    return
                warn(f"[storageOrders] 订单以{status}结束但已有部分成交: "
                     f"orderID={order.get('id', '')} filled={order.get('filled', 0)}")
            if matched is None:
                matched = self._wsRecord(order, wsDir)
                matchedTask = matched['taskName']

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
                'positionOrderIDs': matched.get('positionOrderIDs', []),
            }

            if matched['type'] == kSpot:
                self.__taskHistory.push(**fullRecord)
                self._requestSave()
                log("~~~~__taskHistory~~~~~",self.__taskHistory.buffer())
                return
            # else:
            if matched.get('dir') == kClose:
                fullRecord['dir'] = kClose
            self._updateTaskOrders(matchedTask, matched, fullRecord, status)
            self.__taskHistory.push(**fullRecord)
            self._requestSave()
            log("~~~~__taskHistory~~~~~",self.__taskHistory.buffer())
            
        #消息处理
        result = switchFn({eMarketId['order']: _saveOrder,
                           eMarketId['orderFailed']: _failOrder,
                           eMarketId['orderAccepted']: _acceptOrder,
                           eMarketId['wsOrder']: _wsUpdateOrder,
                           eMarketId['gPosit']: _gPosit,
                           eMarketId['positions']: _verifyPositions,
                           eMarketId['gOpenOrders']: _gOpenOrders,
                           eMarketId['uOpenOrder']: _uOpenOrder,
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

    def _taskExchangePositions(self, symbol: str, account: str = '', taskName: str = '') -> dict:
        grouped: dict[tuple[str, str], dict] = {}
        querySymbol = self._cleanSymbol(symbol)
        taskItems = ((taskName, self.__taskOrders.get(taskName, [])),) if taskName \
            else self.__taskOrders.items()
        for currentTask, orders in taskItems:
            amounts = self._taskOrderAmounts(currentTask, orders)
            for order in orders:
                orderSymbol = self._cleanSymbol(order.get('symbol', ''))
                if querySymbol and querySymbol not in orderSymbol:
                    continue
                side = self._taskOrderSide(order)
                if not side:
                    continue
                amount = amounts.get(str(order.get('orderID') or ''), 0.0)
                if amount <= 0:
                    continue
                key = (orderSymbol, side)
                position = grouped.setdefault(key, {
                    'symbol': orderSymbol,
                    'dir': f"{side == kLong and kBuy or kSell}_{side}",
                    'side': side,
                    'open': order.get('price'),
                    'unRealized': 0,
                    'amount': 0.0,
                    'orderID': order.get('orderID', ''),
                    'orderIDs': [],
                    'taskName': currentTask,
                })
                position['amount'] += amount
                if order.get('orderID'):
                    position['orderIDs'].append(order['orderID'])
        positions = list(grouped.values())
        if not positions:
            return {}
        return {account: positions} if account else {'task': positions}

    def _updateTaskOrders(self, taskName: str, matched: dict, record: dict, status: str = 'closed') -> None:
        direction = self._taskOrderDir(matched, record)
        if not direction:
            return
        if record.get('dir') == kClose:
            requested = self._float(matched.get('amount'))
            filled = self._float(record.get('amt'))
            if status in kOrderFailedStatuses and filled < requested:
                warn(f"[storageOrders] 部分平仓未完成,保留原orderID并按成交量计算剩余仓位: "
                     f"task={taskName} filled={filled}/{requested}")
                return
            self._removeTaskOrders(taskName, matched.get('positionOrderIDs', []))
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

    def _taskOrderAmounts(self, taskName: str, orders: list[dict]) -> dict[str, float]:
        history = self._history()
        amounts: dict[str, float] = {}
        for order in orders:
            orderId = str(order.get('orderID') or '')
            if not orderId:
                continue
            amounts[orderId] = self._historyOrderAmount(history, orderId, order)

        for record in history:
            data = record.get('data', {})
            tags = data.get('tags') or []
            if data.get('dir') != kClose or len(tags) < 2 or tags[1] != taskName:
                continue
            remaining = self._float(data.get('amt'))
            for orderId in data.get('positionOrderIDs') or []:
                orderId = str(orderId)
                current = amounts.get(orderId, 0.0)
                consumed = min(current, remaining)
                amounts[orderId] = current - consumed
                remaining -= consumed
                if remaining <= 0:
                    break
        return amounts

    def _historyOrderAmount(self, history: list[dict], orderId: str, order: dict) -> float:
        if not orderId:
            return self._float(order.get('amount'))
        for record in reversed(history):
            data = record.get('data', {})
            if str(data.get('orderID') or '') != orderId:
                continue
            return self._float(data.get('amt'))
        return self._float(order.get('amount'))

    def _upsertTaskOrder(self, taskName: str, order: dict) -> None:
        orders = self.__taskOrders.setdefault(taskName, [])
        orderID = str(order.get('orderID') or '')
        if not orderID:
            warn(f"[storageOrders] 成交订单缺少orderID,不写入taskOrders: task={taskName}")
            return
        for index, item in enumerate(orders):
            if orderID and str(item.get('orderID') or '') == orderID:
                orders[index] = order
                self._requestSave()
                return
        orders.append(order)
        self._requestSave()

    def _removeTaskOrders(self, taskName: str, orderIDs: list[str]) -> None:
        orders = self.__taskOrders.get(taskName, [])
        if not orders:
            return
        ids = {str(orderID) for orderID in orderIDs if orderID}
        if not ids:
            warn(f"[storageOrders] 平仓缺少被平仓订单ID: task={taskName}")
            return
        self.__taskOrders[taskName] = [
            order for order in orders
            if str(order.get('orderID') or '') not in ids
        ]
        if not self.__taskOrders[taskName]:
            del self.__taskOrders[taskName]
        self._requestSave()

    # 用交易所返回的真实持仓(pos)矫正本地 __taskOrders: 以交易所数据为准
    def _reconcilePositions(self, exName: str, exPositions: list) -> None:
        live = {(self._cleanSymbol(p.get('symbol', '')), (p.get('side') or '').lower()) for p in exPositions}
        for taskName, orders in list(self.__taskOrders.items()):
            keep = []
            for order in orders:
                symbol = self._cleanSymbol(order.get('symbol', ''))
                direction = order.get('dir', '')
                if (symbol, direction) in live:
                    keep.append(order)
                    continue
                log(f"[storageOrders] 持仓矫正: 本地记录 {taskName}/{symbol}/{direction} 交易所已不存在,按交易所数据删除")
            if keep:
                self.__taskOrders[taskName] = keep
            else:
                self.__taskOrders.pop(taskName, None)
            if len(keep) != len(orders):
                self._requestSave()
        localSet = {
            (self._cleanSymbol(o.get('symbol', '')), o.get('dir', ''))
            for orders in self.__taskOrders.values() for o in orders
        }
        for symbol, direction in live - localSet:
            log(f"[storageOrders] 持仓矫正: 交易所持仓 {exName}/{symbol}/{direction} 本地无任何task记录,无法自动归属,请人工核实")

    # 用交易所返回的当前挂单(open)清理本地 __openOrders 里已失效的待匹配记录
    def _reconcileOpenOrders(self, exName: str, exOpenOrders: list) -> None:
        exOrders = self.__openOrders.get(exName)
        if not exOrders:
            return
        liveIds = {str(o.get('clientOrderId') or o.get('orderId') or '') for o in exOpenOrders}
        liveIds.discard('')
        changed = False
        for taskName, taskOrders in list(exOrders.items()):
            for coinId, records in list(taskOrders.items()):
                keep = []
                for rec in records:
                    recId = str(rec.get('clientOrderId') or rec.get('orderID') or '')
                    if recId and recId not in liveIds:
                        log(f"[storageOrders] 挂单矫正: {exName}/{taskName}/{coinId} clientOrderId={rec.get('clientOrderId')} "
                            f"交易所已无此挂单(可能已成交或撤销),历史成交明细无法回溯,移除本地待匹配记录")
                        changed = True
                        continue
                    keep.append(rec)
                if keep:
                    taskOrders[coinId] = keep
                else:
                    del taskOrders[coinId]
            if not taskOrders:
                del exOrders[taskName]
        if not exOrders:
            self.__openOrders.pop(exName, None)
        if changed:
            self._requestSave()

    def _taskName(self, taskName: str | None) -> str:
        return taskName or 'other'

    def _bindOrderId(self, data: dict) -> None:
        orderID = str(data.get('orderID') or '')
        clientOrderId = str(data.get('clientOrderId') or '')
        if not orderID or not clientOrderId:
            return
        exName = data.get('exName', '')
        taskName = self._taskName(data.get('taskName'))
        taskOrders = self.__openOrders.get(exName, {}).get(taskName, {})
        for records in taskOrders.values():
            for record in records:
                if str(record.get('clientOrderId') or '') != clientOrderId:
                    continue
                record['orderID'] = orderID
                self._requestSave()
                return

    def _warnDuplicateOpen(self, exName: str, taskName: str, coinId: str, record: dict) -> None:
        if record.get('type') != kSwap or record.get('dir') not in (kBuy, kSell):
            return
        posSide = record.get('posSide')
        pending = self.__openOrders.get(exName, {}).get(taskName, {}).get(coinId, [])
        active = self.__taskOrders.get(taskName, [])
        duplicate = any(item.get('posSide') == posSide for item in pending)
        if not duplicate:
            targetDir = 'long' if posSide == kLong else 'short' if posSide == kShort else ''
            duplicate = any(
                self._cleanSymbol(item.get('symbol', '')) == self._cleanSymbol(record.get('symbol', ''))
                and item.get('dir') == targetDir
                for item in active
            )
        if duplicate:
            warn(f"[storageOrders] 策略可能失效: task={taskName} {record.get('symbol', '')} "
                 f"{posSide} 短时间重复开仓, 仍按新orderID记录")

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

    def _popTempOrder(self, exName: str, order: dict) -> tuple[dict | None, str]:
        orderId = str(order.get('id') or '')
        clientOrderId = str(order.get('clientOrderId') or order.get('info', {}).get('c') or '')
        return self._popTempOrderBy(
            exName,
            lambda rec: self._sameOrderId(rec, orderId, clientOrderId),
        )

    def _popTempOrderBy(self, exName: str, matchFn: Callable[[dict], bool]) -> tuple[dict | None, str]:
        exOrders = self.__openOrders.get(exName, {})
        for taskName, taskOrders in list(exOrders.items()):
            for coinId, tempData in list(taskOrders.items()):
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
                    self._requestSave()
                    return matched, taskName
        return None, ''

    def _sameOrderId(self, rec: dict, orderId: str, clientOrderId: str) -> bool:
        recOrderId = str(rec.get('orderID') or '')
        recClientOrderId = str(rec.get('clientOrderId') or '')
        if orderId and recOrderId == orderId:
            return True
        return bool(clientOrderId and recClientOrderId == clientOrderId)

    def _fee(self, order: dict) -> dict:
        trades = order.get('trades') or []
        result = self._sumFees(
            fee
            for trade in trades
            for fee in ((trade.get('fees') or []) or [trade.get('fee') or {}])
        )
        if result:
            return result
        result = self._sumFees(order.get('fees') or [])
        if result:
            return result
        result = self._sumFees([order.get('fee') or {}])
        if result:
            return result
        info = order.get('info', {})
        if info.get('N'):
            return {info.get('N'): info.get('n')}
        return {}

    def _sumFees(self, fees: Iterable[dict]) -> dict:
        result: dict[str, float] = {}
        for item in fees:
            currency = item.get('currency') if isinstance(item, dict) else None
            if not currency:
                continue
            result[currency] = result.get(currency, 0.0) + self._float(item.get('cost'))
        return result
