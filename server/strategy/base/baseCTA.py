import abc
from server.utils import pdData, require, err, warn, info, log, spot, swapU, swapC, futureU, futureC, getRootName, slit, str2time
from server.market.consts import kLong, kShort
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
               cumQuote: float = 0, fee: float = 0, status: str = 'open') -> str:
        tags = {'strategy': self._strategy, 'exName': exName, 'category': category,
                'symbol': symbol, 'dir': dir, 'status': status}
        return self._bufOrder.push(tags=tags, lv=lv, orderPrice=orderPrice, avgPrice=avgPrice,
                                   origQty=origQty, cumQuote=cumQuote, fee=fee, orderId=orderId, **tags)
    #更新记录
    def updateRecord(self, uid: str, status: str = '', orderPrice: float = 0,
                     avgPrice: float = 0, origQty: float = 0, cumQuote: float = 0,
                     fee: float = 0, orderId: str = ''):
        params = {'orderPrice': orderPrice, 'avgPrice': avgPrice, 'origQty': origQty,
                  'cumQuote': cumQuote, 'fee': fee}
        if orderId != '':
            params['orderId'] = orderId
        if status != '':
            tags = self._bufOrder.get(id=uid)
            if tags:
                tags['tags']['status'] = status
        self._bufOrder.update(uid, **params)
        if status == 'closed':
            record = self._bufOrder.get(id=uid)
            if record:
                self._updateBook(record, uid)

    def _updateBook(self, record: dict, uid: str):
        """成交后更新 _transactionTrail"""
        tags = record['tags']
        data = record['data']
        category, symbol, dir_str = tags['category'], tags['symbol'], tags['dir']
        avgPrice = float(data.get('avgPrice', 0))
        qty = float(data.get('origQty', 0))
        orderId = str(data.get('orderId', ''))
        lv = int(data.get('lv', 1))

        if 'close' in dir_str:
            # 平仓扣减
            exName = tags.get('exName', '')
            posSide = tags.get('positionSide', '')
            key = f'{category}_{symbol}_{exName}_{posSide}'
            book = self._transactionTrail.get(key)
            if not book:
                return
            book['records'].append({'uid': uid, 'orderId': orderId, 'dir': dir_str})
            totalQty = book['remainQty']
            book['remainQty'] -= qty
            if book['remainQty'] <= 0:
                direction = 1 if posSide == kLong else -1
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
        else:
            # 开仓加仓位
            exName = tags.get('exName', '')
            result = slit(dir_str, '_')
            posSide = result[1] if result else dir_str
            key = f'{category}_{symbol}_{exName}_{posSide}'
            if key not in self._transactionTrail:
                self._transactionTrail[key] = {
                    'records': [], 'remainQty': 0.0, 'avgPrice': 0.0,
                    'totalCost': 0.0, 'lv': lv, 'openTime': str2time('strNow')}
            book = self._transactionTrail[key]
            oldTotal = book['avgPrice'] * book['remainQty']
            book['remainQty'] += qty
            book['avgPrice'] = (oldTotal + avgPrice * qty) / book['remainQty'] if book['remainQty'] else 0
            book['totalCost'] += avgPrice * qty
            book['records'].append({'uid': uid, 'orderId': orderId, 'dir': dir_str})

    #当前还在的持仓的单子
    def overView(self):
        buff = self._bufOrder.get(strategy = self._strategy)
        print("~~~返回订单记录~~~",buff)
    
    def historyOrders(self) -> list[dict]:
        """从 _bufOrder 拼凑完整交易轨迹"""
        all_records = self._bufOrder.get(strategy=self._strategy)
        trails: dict[str, dict] = {}
        for record in all_records:
            tags = record.get('tags', {})
            category, symbol = tags.get('category', ''), tags.get('symbol', '')
            exName = tags.get('exName', '')
            dir_str = tags.get('dir', '')
            result = slit(dir_str, '_')
            posSide = result[1] if result else dir_str
            key = f'{category}_{symbol}_{exName}_{posSide}'
            if key not in trails:
                trails[key] = {'opens': [], 'closes': []}
            if 'close' in dir_str:
                trails[key]['closes'].append(record)
            else:
                trails[key]['opens'].append(record)
        result = []
        for key, group in trails.items():
            result.append({
                'key': key,
                'opens': group['opens'],
                'closes': group['closes'],
                'openCount': len(group['opens']),
                'closeCount': len(group['closes'])})
        return result

    def archive(self):
        self._bufOrder.save2File()

    def reLoad(self, exName: str | list[str] = '', days: int = 7):
        """加载历史记录并对账
        a. 读取文件恢复 _bufOrder
        b. 从 _bufOrder 重建 _transactionTrail
        c. 调用 checkPos 与交易所对账
        """
        self._bufOrder.readFile(days)
        self._transactionTrail.clear()
        for record in self._bufOrder.get(strategy=self._strategy):
            tags = record.get('tags', {})
            if tags.get('status') == 'closed':
                self._updateBook(record, record['id'])
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