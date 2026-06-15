from datetime import datetime, timezone

from server.utils import evtConnect, kEvt_Market, switchFn, pdData, recordBuffer
from server.market import eMarketId, kSpot, kSwap, kBuy, kSell, kClose, kLong, kShort

class storageOrders:
    "订单/状态事件 监听"

    def __init__(self):
        self.__holdings: dict[str, list] = {}   # 交易所现持有的原始订单数据
        self.__taskOrders = recordBuffer()      # task正在持有的订单
        self.__taskHistory = recordBuffer()     # 任务历史订单
        self.__tempOrders = {}                  #task临时记录
        #todo:读取__taskOrders保存的文件
        evtConnect(kEvt_Market, self)

    def evtProcess(self, key, *args):
        id, exName = args[0], args[1] if len(args) > 2 else None
        # 持仓记录
        def _initHoldings():
            key, data = args[2],args[3]
            self.__holdings.setdefault(exName, {}).setdefault(key, {}).update(data)
            print("持仓记录:\n", self.__holdings)
            # todo:修改,先加载__taskOrders,看看能不能对应上__holdings
        
        #返回持仓
        def _gPosit():
            queryType, symbol = args[2], args[3]
            # queryType: 'task'从运行任务中找 / 'ex'从交易所中寻找
            if queryType == 'task':
                return self.__taskOrders.filter(lambda x: x.get('symbol') == symbol)
            # 'ex': 从交易所原始持仓中查找
            result = {}
            for exName, holdings in self.__holdings.items():
                posList = holdings.get('pos', [])
                for p in posList:
                    sym = p.get('symbol', '') if isinstance(p, dict) else ''
                    if symbol and symbol not in sym:
                        continue
                    result.setdefault(exName, []).append(p)
            return result

        # 记录oms通过的订单
        def _saveOrder():
            data = args[1] if len(args) > 1 else {}
            symbol = data.get('symbol', '')
            direction = data.get('dir', '')
            taskName = data.get('taskName', '')
            coinId = data.get("coinInfo")['id']
            exName = data.get('exName', '')
            orderType = data.get('type', '')
            record = {
                'dir': direction,
                'type': orderType,
                'posSide': data.get('posSide'),
                'price': data.get('price'),
                'amount': data.get('amount'),
                'totelPrice': data.get('totelPrice', 0),
                'taskName': taskName,
            }
            self.__tempOrders.setdefault(exName, {}).setdefault(coinId, []).append(record)
            print("~~~~_saveOrder~~~~",self.__tempOrders)
            print(f"[storageOrders] 暂存订单: {exName} {coinId} {direction}")

        # ws订单数据更新
        def _wsUpdateOrder():
            order = args[2] if len(args) > 2 else {}
            info = order.get('info', {})
            if not info:
                return
            print("~~~~~~orderdata~~~~~~~",order)
            # print("~~~~~~__tempOrders~~~~~~~",self.__tempOrders)
            coinId = info.get('s', '')
            wsPs = info.get('ps', None)           # 持仓方向: LONG/SHORT/None(现货)
            wsSide = order.get('side', '')        # 'buy' / 'sell'
            isReduce = order.get('reduceOnly', False)
            
            # 确定 WS 对应的 dir (kBuy/kSell/kClose)
            if isReduce and wsPs is not None:
                wsDir = kClose
            else:
                wsDir = kBuy if wsSide == 'buy' else kSell
            print("~~~~~~value~~~~~~~",wsDir,exName,coinId)
            # exName 即交易所 classId, 直接定位 __tempOrders
            exOrders = self.__tempOrders.get(exName, {})
            tempData = exOrders.get(coinId)
            if not tempData:
                return

            # 匹配: dir 必须相等; 合约开仓还要 posSide 一致; 平仓按相反方向匹配
            matched = None
            for i, rec in enumerate(tempData):
                recDir = rec.get('dir', '')
                recPos = rec.get('posSide')
                print("~~~~find tempData~~~~",recDir,recPos)
                print("~~~~find ws~~~~",wsPs, wsSide)
                if recDir != wsDir:
                    continue

                if wsDir == kClose:
                    # 平仓: wsPs 是原始持仓方向, recPos 已被 oms._close 翻转
                    # 平 LONG → wsPs=LONG, recPos=SHORT
                    if (wsPs == kLong and recPos == kShort) or \
                       (wsPs == kShort and recPos == kLong):
                        matched = tempData.pop(i)
                        break
                elif wsPs is not None:
                    # 合约开仓: posSide 必须一致
                    if recPos == wsPs:
                        matched = tempData.pop(i)
                        break
                else:
                    # 现货: 无 posSide, dir 相等即可
                    matched = tempData.pop(i)
                    break

            if matched is None:
                return

            # 清理 __tempOrders 空层级 (pop(i) 已按 index 移除条目, 此处仅清理空容器)
            if not tempData:
                del exOrders[coinId]
            if not exOrders:
                del self.__tempOrders[exName]

            # 订单时间: 使用 WS 返回的 timestamp (ms → datetime)
            wsTs = order.get('timestamp', 0)
            orderTime = datetime.fromtimestamp(wsTs / 1000, tz=timezone.utc) if wsTs else datetime.now(timezone.utc)

            # 平仓时获取持仓开仓价 + 清理已平持仓
            openPrice = None
            if wsDir == kClose:
                filledAmt = float(order.get('filled', 0))
                for configName, data in self.__holdings.get(exName, {}).items():
                    posList = data.get('pos', [])
                    for j, pos in enumerate(posList):
                        if pos.get('symbol', '') == coinId:
                            openPrice = float(pos.get('open', 0))
                            # 全部平完则移除该持仓 index
                            if filledAmt >= float(pos.get('amount', 0)):
                                posList.pop(j)
                            break
                    if openPrice is not None:
                        break

            # 合并 WS 数据
            fullRecord = {
                'time': orderTime,
                'tags': [exName, matched.get('taskName', ''), coinId],
                'symbol': matched.get('symbol'),
                'orderID': order.get('id', ''),
                'price': order.get('average'),                  # 成交均价 (=开仓价 或 平仓价)
                'openPrice': openPrice,                         # 开仓价 (平仓时从持仓取)
                'total': order.get('cost', 0),                  # 总金额
                'amt': order.get('filled', 0),                  # 已成交数量
                'fee': {info.get('N'): info.get('n')},          # 手续费 (币种:数量)
                'profit': info.get('rp'),                       # 已实现盈亏
            }

            if matched['type'] == kSpot:
                self.__taskHistory.push(**fullRecord)
                # print(f"[storageOrders] 现货→历史: {coinId} {wsSide}")
            else:
                self.__taskOrders.push(**fullRecord)
                self.__taskHistory.push(**fullRecord)
                # print(f"[storageOrders] 合约→活跃+历史: {coinId} {wsSide}")
            print("~~~~~~fullRecord~~~~~~~~",fullRecord)
            print("~~~~~~tempData~~~~~",matched)
            print("~~~~__tempOrders~~~~~",self.__tempOrders)
            print("~~~~__taskHistory~~~~~",self.__taskHistory)
            print("~~~~__taskOrders~~~~~",self.__taskOrders)

        switchFn({eMarketId['positions']: _initHoldings,
                  eMarketId['order']: _saveOrder,
                  eMarketId['wsOrder']: _wsUpdateOrder,
                  eMarketId['gPosit']: _gPosit,
                }, key=id)
        

#init demoVwap
# ~~~~init test~~~~
# ~~~~ws 开始监听~~~
# ~~~~~~update_10s~~~~~~~~
# ~~~~_saveOrder~~~~ {'binanceMain': {'DOGEUSDT': [{'dir': 'buy', 'type': 'spot', 'posSide': None, 'price': 0.09029, 'amount': 12.0, 'totelPrice': 1, 'taskName': 'test'}]}}
# [storageOrders] 暂存订单: binanceMain DOGEUSDT buy
# [SPOT] 资金更新: USDT 可用 = 5.65708:{'info': {'e': 'outboundAccountPosition', 'E': 1781540244146, 'u': 1781540244146, 'B': [{'a': 'BNB', 'f': '0.00000000', 'l': '0.00000000'}, {'a': 'USDT', 'f': '5.65708000', 'l': '1.08348000'}, {'a': 'DOGE', 'f': '35.96400000', 'l': '0.00000000'}]}, 'BNB': {'free': 0.0, 'used': 0.0, 'total': 0.0}, 'USDT': {'free': 5.65708, 'used': 1.08348, 'total': 6.74056}, 'DOGE': {'free': 35.964, 'used': 0.0, 'total': 35.964}, 'timestamp': 1781540244146, 'datetime': '2026-06-15T16:17:24.146Z', 'free': {'BNB': 0.0, 'USDT': 5.65708, 'DOGE': 35.964}, 'used': {'BNB': 0.0, 'USDT': 1.08348, 'DOGE': 0.0}, 'total': {'BNB': 0.0, 'USDT': 6.74056, 'DOGE': 35.964}}
# ~~~~~~orderdata~~~~~~~[SPOT] 资金更新: USDT 可用 = 5.65708:{'info': {'e': 'outboundAccountPosition', 'E': 1781540254675, 'u': 1781540254675, 'B': [{'a': 'BNB', 'f': '0.00000000', 'l': '0.00000000'}, {'a': 'USDT', 'f': '5.65708000', 'l': '0.00000000'}, {'a': 'DOGE', 'f': '47.95200000', 'l': '0.00000000'}]}, 'BNB': {'free': 0.0, 'used': 0.0, 'total': 0.0}, 'USDT': {'free': 5.65708, 'used': 0.0, 'total': 5.65708}, 'DOGE': {'free': 47.952, 'used': 0.0, 'total': 47.952}, 'timestamp': 1781540254675, 'datetime': '2026-06-15T16:17:34.675Z', 'free': {'BNB': 0.0, 'USDT': 5.65708, 'DOGE': 47.952}, 'used': {'BNB': 0.0, 'USDT': 0.0, 'DOGE': 0.0}, 'total': {'BNB': 0.0, 'USDT': 5.65708, 'DOGE': 47.952}} {'info': {'e': 'executionReport', 'E': 1781540254675, 's': 'DOGEUSDT', 'c': 'x-TKT5PX2F824c92a8ec16f6094f6319', 'S': 'BUY', 'o': 'LIMIT', 'f': 'GTC', 'q': '12.00000000', 'p': '0.09029000', 'P': '0.00000000', 'F': '0.00000000', 'g': -1, 'C': '', 'x': 'TRADE', 'X': 'FILLED', 'r': 'NONE', 'i': 14587939263, 'l': '12.00000000', 'z': '12.00000000', 'L': '0.09029000', 'n': '0.01200000', 'N': 'DOGE', 'T': 1781540254675, 't': 1566874555, 'I': 31150074679, 'w': False, 'm': True, 'M': True, 'O': 1781540244146, 'Z': '1.08348000', 'Y': '1.08348000', 'Q': '0.00000000', 'W': 1781540244146, 'V': 'EXPIRE_MAKER'}, 'symbol': 'DOGE/USDT', 'id': '14587939263', 'clientOrderId': 'x-TKT5PX2F824c92a8ec16f6094f6319', 'timestamp': 1781540244146, 'datetime': '2026-06-15T16:17:24.146Z', 'lastTradeTimestamp': 1781540254675, 'lastUpdateTimestamp': 1781540254675, 'type': 'limit', 'timeInForce': 'GTC', 'postOnly': False, 'reduceOnly': None, 'side': 'buy', 'price': 0.09029, 'stopPrice': 0.0, 'triggerPrice': 0.0, 'amount': 12.0, 'cost': 1.08348, 'average': 0.09029, 'filled': 12.0, 'remaining': 0.0, 'status': 'closed', 'fee': {'currency': 'DOGE', 'cost': 0.012}, 'trades': [{'info': {'e': 'executionReport', 'E': 1781540254675, 's': 'DOGEUSDT', 'c': 'x-TKT5PX2F824c92a8ec16f6094f6319', 'S': 'BUY', 'o': 'LIMIT', 'f': 'GTC', 'q': '12.00000000', 'p': '0.09029000', 'P': '0.00000000', 'F': '0.00000000', 'g': -1, 'C': '', 'x': 'TRADE', 'X': 'FILLED', 'r': 'NONE', 'i': 14587939263, 'l': '12.00000000', 'z': '12.00000000', 'L': '0.09029000', 'n': '0.01200000', 'N': 'DOGE', 'T': 1781540254675, 't': 1566874555, 'I': 31150074679, 'w': False, 'm': True, 'M': True, 'O': 1781540244146, 'Z': '1.08348000', 'Y': '1.08348000', 'Q': '0.00000000', 'W': 1781540244146, 'V': 'EXPIRE_MAKER'}, 'timestamp': 1781540254675, 'datetime': '2026-06-15T16:17:34.675Z', 'symbol': 'DOGE/USDT', 'id': '1566874555', 'order': '14587939263', 'type': 'limit', 'takerOrMaker': 'maker', 'side': 'buy', 'price': 0.09029, 'amount': 12.0, 'cost': 1.08348, 'fee': {'currency': 'DOGE', 'cost': 0.012}, 'fees': [{'currency': 'DOGE', 'cost': 0.012}]}], 'fees': [], 'takeProfitPrice': None, 'stopLossPrice': None}

# ~~~~~~value~~~~~~~ buy binanceMain DOGEUSDT
# ~~~~find tempData~~~~ buy None
# ~~~~find ws~~~~ None buy
# ~~~~~~fullRecord~~~~~~~~ {'time': datetime.datetime(2026, 6, 15, 16, 17, 24, 146000, tzinfo=datetime.timezone.utc), 'tags': ['binanceMain', 'test', 'DOGEUSDT'], 'symbol': None, 'orderID': '14587939263', 'price': 0.09029, 'openPrice': None, 'total': 1.08348, 'amt': 12.0, 'fee': {'DOGE': '0.01200000'}, 'profit': None}
# ~~~~~~tempData~~~~~ {'dir': 'buy', 'type': 'spot', 'posSide': None, 'price': 0.09029, 'amount': 12.0, 'totelPrice': 1, 'taskName': 'test'}
# ~~~~__tempOrders~~~~~ {}
# ~~~~__taskHistory~~~~~ <server.utils.recordBuffer.recordBuffer object at 0x0000021AAB0354D0>
# ~~~~__taskOrders~~~~~ <server.utils.recordBuffer.recordBuffer object at 0x0000021AAB035410>