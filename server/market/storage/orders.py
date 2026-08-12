import os
from datetime import datetime, timezone
from typing import Callable
from server.utils import evtConnect, kEvt_Market, switchFn, recordBuffer,log, readFile, writeFile, debouncedSaver
from server.utils.fileConfig import kOtherPath
from server.market import eMarketId, kSpot, kSwap, kBuy, kSell, kClose, kLong, kShort, kCancel

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
                'time': self._orderTime(None),
            }
            self.__openOrders.setdefault(exName, {}).setdefault(taskName, {}).setdefault(coinId, []).append(record)
            self._requestSave()
            # log("~~~~oms_saveOrder~~~~",self.__openOrders)

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

            matched, matchedTask = self._popTempOrder(exName, coinId, order)

            if matched is None:
                if wsDir == kClose and order.get('status') == 'closed':
                    matched, matchedTask = self._matchManualCloseOrder(order, wsPs)
            if matched is None:
                matched = self._wsRecord(order, wsDir)
                matchedTask = matched['taskName']
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
                self._requestSave()
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
                self._requestSave()
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
                           eMarketId['positions']: _verifyPositions,
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
        for record in reversed(self._history()):
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
                self._requestSave()
                return
        orders.append(order)
        self._requestSave()

    def _removeTaskOrder(self, taskName: str, symbol: str, direction: str) -> None:
        orders = self.__taskOrders.get(taskName, [])
        cleanSymbol = self._cleanSymbol(symbol)
        self.__taskOrders[taskName] = [
            order for order in orders
            if self._cleanSymbol(order.get('symbol', '')) != cleanSymbol or order.get('dir') != direction
        ]
        if not self.__taskOrders[taskName]:
            del self.__taskOrders[taskName]
        self._requestSave()

    # 用交易所返回的真实持仓(pos)矫正本地 __taskOrders: 以交易所数据为准
    def _reconcilePositions(self, exName: str, exPositions: list) -> None:
        live = {(self._cleanSymbol(p.get('symbol', '')), (p.get('side') or '').lower()) for p in exPositions}
        for taskName, orders in list(self.__taskOrders.items()):
            for order in list(orders):
                symbol = self._cleanSymbol(order.get('symbol', ''))
                direction = order.get('dir', '')
                if (symbol, direction) in live:
                    continue
                log(f"[storageOrders] 持仓矫正: 本地记录 {taskName}/{symbol}/{direction} 交易所已不存在,按交易所数据删除")
                self._removeTaskOrder(taskName, order.get('symbol', ''), direction)
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

    def _popTempOrder(self, exName: str, coinId: str, order: dict) -> tuple[dict | None, str]:
        orderId = str(order.get('id') or '')
        clientOrderId = str(order.get('clientOrderId') or order.get('info', {}).get('c') or '')
        return self._popTempOrderBy(
            exName,
            coinId,
            lambda rec: self._sameOrderId(rec, orderId, clientOrderId),
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
                self._requestSave()
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
