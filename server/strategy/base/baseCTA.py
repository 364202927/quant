import abc
from server.utils import pdData, require, err, warn, info, log, spot, swapU, swapC, futureU, futureC, getRootName, slit, str2time
from server.market.consts import kLong, kShort, kSwap, kFuture, kDelivery, kSpot, kBuy, kSell
from server.core.task import taskHandle
from server.utils.fileConfig import g_config, kLogBufType, kOrderBufType, recordBuffer
kIndicatorsFile = 'server.indicators.'

class baseCTA(taskHandle):
    "交易基类"

    def __init__(self):
        super().__init__()
        self._strategy = getRootName(self.__class__, 'strategy')    #交易策略名字
        self._bufOrder:recordBuffer = g_config.get(kOrderBufType)   #订单记录
        self._transactionTrail = {}                                 #交易轨迹,只记录非现货{f'{category}_{symbol}_{exName}_{posSide}':{交易轨迹[]=[记录的uid],剩余持仓}}
        self._history=[]                                            #记录每次完整的交易记录轨迹(开仓~平仓)

    def regIndicators(self, dict):
        dictIndicator = {}
        for name, indicatorName in dict.items():
            indicator = require(kIndicatorsFile + indicatorName)()
            setattr(self, name, indicator)
            dictIndicator[name] = indicator
        #保存指标到共享
        self.indicators[self.className()] = dictIndicator

    #记录
    def record(self, exName: str, category: str, symbol: str, orderId: str, lv: int, dir: str,
               orderPrice: float = 0, avgPrice: float = 0, origQty: float = 0,
               cumQuote: float = 0, fee: float = 0) -> str:
        tags = {'strategy': self._strategy, 'exName': exName, 'category': category,
                'symbol': symbol, 'dir': dir}
        uid = self._bufOrder.push(tags=tags, lv=lv, orderPrice=orderPrice, avgPrice=avgPrice,
                                   origQty=origQty, cumQuote=cumQuote, fee=fee, orderId=orderId, **tags)
        # 合约时初始化轨迹
        if category in (kSwap, kFuture, kDelivery):
            posSide = dir.split('_')[1] if '_' in dir else dir
            key = f'{category}_{symbol}_{exName}_{posSide}'
            if key not in self._transactionTrail:
                self._transactionTrail[key] = {
                    'records': [], 'remainQty': 0.0, 'avgPrice': 0.0,
                    'totalCost': 0.0, 'lv': lv, 'openTime': str2time('strNow')}
        return uid
    #更新记录
    def updateRecord(self, uid: str, orderPrice: float = 0,
                     avgPrice: float = 0, origQty: float = 0, cumQuote: float = 0,
                     fee: float = 0, orderId: str = ''):
        params = {'orderPrice': orderPrice, 'avgPrice': avgPrice, 'origQty': origQty,
                  'cumQuote': cumQuote, 'fee': fee}
        if orderId != '':
            params['orderId'] = orderId
        self._bufOrder.update(uid, **params)
        # 合约时更新持仓轨迹
        record = self._bufOrder.get(id=uid)
        if record:
            category = record['tags'].get('category', '')
            if category in (kSwap, kFuture, kDelivery):
                exName = record['tags'].get('exName', '')
                self._updateBook(record, uid, exName)

    def _updateBook(self, record: dict, uid: str, exName: str):
        """更新合约持仓轨迹和PnL计算"""
        tags = record['tags']
        data = record['data']
        category = tags.get('category', '')
        symbol = tags.get('symbol', '')
        dir_str = tags.get('dir', '')

        # 提取成交数据
        avgPrice = float(data.get('avgPrice', 0))
        qty = float(data.get('origQty', 0))
        if qty == 0:
            return

        # 解析持仓方向和交易动作
        result = slit(dir_str, '_')
        state = result[0] if result else dir_str     # 'buy' or 'sell'
        posSide = result[1] if result else dir_str   # 'LONG' or 'SHORT'

        key = f'{category}_{symbol}_{exName}_{posSide}'

        if key not in self._transactionTrail:
            return  # 异常情况，不处理

        book = self._transactionTrail[key]

        # 判断开仓/平仓: LONG+buy=开仓, SHORT+sell=开仓, 其余=平仓
        isOpen = (posSide == kLong and state == kBuy) or (posSide == kShort and state == kSell)

        # 保存修改前的持仓量，用于平仓结算
        oldRemainQty = book['remainQty']

        # 更新持仓数据
        if isOpen:
            oldTotal = book['avgPrice'] * book['remainQty']
            book['remainQty'] += qty
            book['avgPrice'] = (oldTotal + avgPrice * qty) / book['remainQty'] if book['remainQty'] else 0
            book['totalCost'] += avgPrice * qty
        else:
            book['remainQty'] -= qty
        book['records'].append({'uid': uid, 'orderId': data.get('orderId', ''), 'dir': dir_str})

        # 平仓结算
        if book['remainQty'] <= 0:
            direction = 1 if posSide == kLong else -1
            totalQty = oldRemainQty  # 平仓前的持仓量
            pnl = (avgPrice - book['avgPrice']) * totalQty * direction
            pnlRate = pnl / book['totalCost'] if book['totalCost'] else 0
            self._history.append({
                'key': key,
                'records': book['records'],
                'avgPrice': book['avgPrice'],
                'closePrice': avgPrice,
                'totalQty': totalQty,
                'lv': book['lv'],
                'pnl': round(pnl, 6),
                'pnlRate': round(pnlRate, 6),
                'openTime': book.get('openTime', ''),
                'closeTime': str2time('strNow')})
            del self._transactionTrail[key]

    #当前还在的持仓的单子
    def overView(self):
        buff = self._bufOrder.get(strategy = self._strategy)
        print("~~~返回订单记录~~~",buff)
    
    def historyOrders(self) -> list[dict]:
        """返回已完成的交易历史"""
        return self._history

    def archive(self):
        self._bufOrder.save2File()

    def reLoad(self, exName: str | list[str] = '', days: int = 7):
        """加载历史记录并与交易所对账"""
        self._bufOrder.readFile(days)
        self._transactionTrail.clear()
        self._history.clear()

        # 遍历合约记录，重建轨迹
        all_records = self._bufOrder.get(strategy=self._strategy)
        if not all_records:
            return

        for record in all_records:
            tags = record.get('tags', {})
            category = tags.get('category', '')
            if category in (kSpot, ''):
                continue  # 现货和空类别跳过
            exName_r = tags.get('exName', '')
            dir_str = tags.get('dir', '')
            result = slit(dir_str, '_')
            posSide = result[1] if result else dir_str
            symbol = tags.get('symbol', '')
            key = f'{category}_{symbol}_{exName_r}_{posSide}'
            # 初始化 _transactionTrail（如不存在）
            if key not in self._transactionTrail:
                self._transactionTrail[key] = {
                    'records': [], 'remainQty': 0.0, 'avgPrice': 0.0,
                    'totalCost': 0.0, 'lv': int(record.get('data', {}).get('lv', 1)),
                    'openTime': record.get('time', str2time('strNow'))}
            self._updateBook(record, record['id'], exName_r)

        # 与交易所对账
        targets = self._exName if exName == '' else (exName if isinstance(exName, list) else [exName])
        for name in targets:
            self.checkPos(name)
    
    # 初始化
    @abc.abstractmethod
    def init(self): pass

    # 接收时间回调
    # def stopProcess(self) 任务被设为停止时，只会触发停止回调
    # def process(tabId, timeKey) 在所有时间前调用,retrun true后续不再触发其余时间回调
    # def update_(timeKey)(tabId, timeKey) 正常时间回调
    # def update_1sLess(tabId, timeKey) 少于1秒