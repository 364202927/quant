from server.strategy.base.baseCTA import *
from server.market import g_marketMgr

class contractCTA(baseCTA):
    '辅助合约交易'

    def __init__(self):
        super().__init__()
        self._transactionTrail = {}                                 #交易轨迹
        self._history=[]                                            #记录每次完整的交易记录轨迹(开仓~平仓)

    #返回历史交易
    def historyOrders(self, symbols: list[str], exName: list[str] | None = None) -> list[dict]:
        def _mergeOrder(trades: list[dict]) -> list[dict]:
            trades.sort(key=lambda t: t['time'])
            merged: dict[str, dict] = {}
            for t in trades:
                oid = t.get('orderId', '')
                if oid and oid in merged:
                    m = merged[oid]
                    oldQty, newQty = m['qty'], t['qty']
                    totalQty = oldQty + newQty
                    m['price'] = round((m['price'] * oldQty + t['price'] * newQty) / totalQty, 8) if totalQty else 0
                    m['qty'] = totalQty
                    m['cost'] += t.get('cost', 0)
                    m['fee'] += t['fee']
                    m['realizedPnl'] += t['realizedPnl']
                    m['time'] = max(m['time'], t['time'])
                else:
                    merged[oid or f'_no_id_{id(t)}'] = {**t}
            result = list(merged.values())
            result.sort(key=lambda t: t['time'])
            return result
        
        def _collectTrails(trades: list[dict], cleanSymbol: str) -> None:
            trail: dict | None = None
            remainQty = 0.0
            for t in trades:
                if trail is None:
                    trail = {
                        'symbol': cleanSymbol or t['symbol'],
                        'beginTime': t['time'], 'completed': True,
                        'totalFee': 0.0, 'lv': 0, 'pnl': 0.0,
                        'transactionTrail': []}

                dir_str = f"{t['side']}_{t['positionSide']}" if t['positionSide'] else t['side']
                trail['transactionTrail'].append({
                    'dir': dir_str,
                    'price': t['price'],
                    'qty': t['qty'],
                    'fee': t['fee']})
                trail['totalFee'] += t['fee']

                if t['realizedPnl'] == 0:
                    remainQty += t['qty']
                else:
                    remainQty -= t['qty']
                    trail['pnl'] += t['realizedPnl']

                if remainQty <= 0 and trail['pnl'] != 0:
                    trail['duration'] = round((t['time'] - trail['beginTime']) / 3600000, 2)
                    trail['totalFee'] = round(trail['totalFee'], 6)
                    trail['pnl'] = round(trail['pnl'], 6)
                    self._history.append(trail)
                    trail = None
                    remainQty = 0.0
            if trail is not None:
                trail['completed'] = False
                trail['duration'] = 0
                trail['totalFee'] = round(trail['totalFee'], 6)
                trail['pnl'] = round(trail['pnl'], 6)
                self._history.append(trail)

        def _collectSpotTrails(trades: list[dict], cleanSymbol: str) -> None:
            trail: dict | None = None
            remainQty = 0.0
            for t in trades:
                if trail is None:
                    trail = {
                        'symbol': cleanSymbol or t['symbol'],
                        'beginTime': t['time'], 'completed': True,
                        'totalFee': 0.0,
                        'transactionTrail': []}

                trail['transactionTrail'].append({
                    'dir': t['side'],
                    'price': t['price'],
                    'qty': t['qty'],
                    'fee': t['fee']})
                trail['totalFee'] += t['fee']
                remainQty += t['qty'] if t['side'] == 'buy' else -t['qty']

                if remainQty <= 0:
                    trail['duration'] = round((t['time'] - trail['beginTime']) / 3600000, 2)
                    trail['totalFee'] = round(trail['totalFee'], 6)
                    self._history.append(trail)
                    trail = None
                    remainQty = 0.0
            if trail is not None:
                trail['completed'] = False
                trail['duration'] = 0
                trail['totalFee'] = round(trail['totalFee'], 6)
                self._history.append(trail)
        #logic
        self._history.clear()
        targets = self._exName if exName is None else exName
        for name in targets:
            ex = g_marketMgr.get(name)
            if not ex:
                continue
            for symbol in symbols:
                category, cleanSymbol = slit(symbol, '_')
                trades = ex.trades(symbol)
                if not trades:
                    continue
                merged = _mergeOrder(trades)

                sides: dict[str, list] = {}
                for t in merged:
                    sides.setdefault(t.get('positionSide', ''), []).append(t)
                fn = _collectSpotTrails if category == kSpot else _collectTrails
                for side_trades in sides.values():
                    fn(side_trades, cleanSymbol)
        return self._history
        
    def archive(self):
        # self._bufOrder.save2File()
        super().archive()

    #重加载历史记录与交易轨迹
    def reLoad(self, exName: str | list[str] = '', days: int = 7):
        super().reLoad()
        self._transactionTrail.clear()
        self._history.clear()

        # # 遍历合约记录，重建轨迹
        # all_records = self._bufOrder.get(strategy=self._strategy)
        # if not all_records:
        #     return

        # for record in all_records:
        #     tags = record.get('tags', {})
        #     category = tags.get('category', '')
        #     if category in (kSpot, ''):
        #         continue  # 现货和空类别跳过
        #     exName_r = tags.get('exName', '')
        #     dir_str = tags.get('dir', '')
        #     result = slit(dir_str, '_')
        #     posSide = result[1] if result else dir_str
        #     symbol = tags.get('symbol', '')
        #     key = f'{category}_{symbol}_{exName_r}_{posSide}'
        #     # 初始化 _transactionTrail（如不存在）
        #     if key not in self._transactionTrail:
        #         self._transactionTrail[key] = {
        #             'records': [], 'remainQty': 0.0, 'avgPrice': 0.0,
        #             'totalCost': 0.0, 'lv': int(record.get('data', {}).get('lv', 1)),
        #             'openTime': record.get('time', str2time('strNow'))}
        #     self._updateBook(record, record['id'], exName_r)

        # # 与交易所对账
        # targets = self._exName if exName == '' else (exName if isinstance(exName, list) else [exName])
        # for name in targets:
        #     self.checkPos(name)



