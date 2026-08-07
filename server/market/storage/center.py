import copy
from server.utils import evtConnect, evtFireAsync, kEvt_Market,switchFn,log
from server.market import eMarketId, kBuy, kSell,kPm

class storageCenter:
    "个人资产数据缓存"

    def __init__(self):
        self.__snapshot: dict[str, dict] = {}  # {okx: {'main': {},... },bybit:{'xx':{}},...}
        self.__spotCost: dict[str, list[dict]] = {}     # {coinId: [现货成交成本轨迹]}
        evtConnect(kEvt_Market, self)

    def evtProcess(self, key, *args):
        id_, exName = args[0], args[1] if len(args) > 2 else None
        def _balanceUpdate(exName,key,data):
            target = self.__snapshot.setdefault(exName, {}).setdefault(key, {})
            self._mergeBalance(target, data)
        #evt事件
        def _balance():
            key, data = args[2],args[3]
            _balanceUpdate(exName, key, data)
            self._logSnapshot(exName, key)
            self._logSpotBalance(exName, key, "[center.balance] spot账号余额:")

        def _increment():
            key, data = args[2],args[3]
            cleanData = self._cleanWsBalance(data)
            if cleanData:
                _balanceUpdate(exName, key, cleanData)
                if self._pruneSpotCost(cleanData.get('total', {})):
                    log("ws 更新现货成本轨迹:",self.__spotCost)
                self._logSpotBalance(exName, key, "[center.wsBalance] spot账号余额:")
            # print("~~~~updata balance~~~~~~~~",exName,key, data)
            # log("ws 更新storageCenter账号详情:")
            # logFormat(self.__snapshot[exName][key][kPm])

        def _wsOrder():
            order = args[2] if len(args) > 2 else {}
            if self._updateSpotCost(order):
                log("ws 更新现货成本轨迹:",self.__spotCost)
                # logFormat(self.__spotCost)

        return switchFn({eMarketId['balance']: _balance,
                  eMarketId['wsBalance']: _increment,
                  eMarketId['wsOrder']: _wsOrder,
                  eMarketId['gBalance']: self._getBalance},
                  key=id_)
    
    def _getBalance(self) -> dict:
        return copy.deepcopy(self.__snapshot)

    def _cleanWsBalance(self, data: dict) -> dict:
        if not isinstance(data, dict):
            return {}
        if data.get('info', {}).get('fs') in ('UM', 'CM'):
            return {}
        clean = {}
        for key in ('free', 'total'):
            value = data.get(key)
            if not isinstance(value, dict):
                continue
            clean[key] = {
                coin: float(amount)
                for coin, amount in value.items()
                if amount is not None
            }
        return clean

    def _mergeBalance(self, target: dict, data: dict) -> None:
        for key, value in data.items():
            value = copy.deepcopy(value)
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                target[key].update(value)
            else:
                target[key] = value

    def _logSnapshot(self, exName: str, account: str) -> None:
        pmData = self.__snapshot.get(exName, {}).get(account, {}).get(kPm, {})
        log("[center.balance] __snapshot REST更新:",
            {'exName': exName, 'account': account, 'free': pmData.get('free'),
             'equity': pmData.get('equity'), 'USDT': pmData.get('total', {}).get('USDT')})

    def _logSpotBalance(self, exName: str, account: str, title: str) -> None:
        data = self.__snapshot.get(exName, {}).get(account, {})
        log(title, {
            'exName': exName,
            'account': account,
            'free': data.get('free', {}),
            'total': data.get('total', {}),
        })

    def _updateSpotCost(self, order: dict) -> bool:
        if not self._isSpotFilledOrder(order):
            return False
        coinId = self._coinId(order)
        if not coinId:
            return False
        side = order.get('side')
        if side == kBuy:
            lot = self._spotCostLot(order)
            if lot['amount'] <= 0:
                return False
            self.__spotCost.setdefault(coinId, []).append(lot)
            return True
        if side == kSell:
            return self._reduceSpotCost(coinId, self._float(order.get('filled')))
        return False

    def _isSpotFilledOrder(self, order: dict) -> bool:
        if not isinstance(order, dict) or order.get('status') != 'closed':
            return False
        info = order.get('info', {})
        return not order.get('reduceOnly') and not info.get('ps')

    def _coinId(self, order: dict) -> str:
        info = order.get('info', {})
        coinId = info.get('s', '')
        if coinId:
            return coinId
        symbol = order.get('symbol', '')
        return symbol.replace('/', '').split(':')[0]

    def _spotCostLot(self, order: dict) -> dict:
        coinId = self._coinId(order)
        baseCoin = self._baseCoin(coinId)
        amount = self._float(order.get('filled')) - self._baseFee(order, baseCoin)
        price = self._float(order.get('average') or order.get('price'))
        return {
            'amount': amount,
            'price': price,
        }

    def _baseFee(self, order: dict, baseCoin: str) -> float:
        fee = order.get('fee') or {}
        if fee.get('currency') == baseCoin:
            return self._float(fee.get('cost'))
        info = order.get('info', {})
        if info.get('N') == baseCoin:
            return self._float(info.get('n'))
        fees = order.get('fees') or []
        return sum(
            self._float(item.get('cost'))
            for item in fees
            if item.get('currency') == baseCoin
        )

    def _reduceSpotCost(self, coinId: str, amount: float) -> bool:
        lots = self.__spotCost.get(coinId)
        if not lots or amount <= 0:
            return False
        remaining = amount
        while lots and remaining > 0:
            lot = lots[0]
            lotAmount = self._float(lot.get('amount'))
            if lotAmount <= remaining:
                remaining -= lotAmount
                lots.pop(0)
                continue
            lot['amount'] = lotAmount - remaining
            remaining = 0
        if not lots:
            del self.__spotCost[coinId]
        return True

    def _pruneSpotCost(self, total: dict) -> bool:
        if not isinstance(total, dict):
            return False
        changed = False
        for coinId in list(self.__spotCost):
            baseCoin = self._baseCoin(coinId)
            coinAmount = self._float(total.get(baseCoin))
            if baseCoin and coinAmount <= 0:
                del self.__spotCost[coinId]
                changed = True
            elif baseCoin and self._isDustValue(coinId, coinAmount):
                changed = self._syncDustSpotCost(coinId, coinAmount) or changed
        return changed

    # 现货仓位市值(按当前均价估算)是否低于 1u,低于则收敛成 1 条成本轨迹
    def _isDustValue(self, coinId: str, coinAmount: float) -> bool:
        price = self._avgSpotPrice(self.__spotCost.get(coinId, []))
        return price > 0 and coinAmount * price < 1

    def _syncDustSpotCost(self, coinId: str, coinAmount: float) -> bool:
        lots = self.__spotCost.get(coinId)
        if not lots or coinAmount <= 0:
            return False
        avgPrice = self._avgSpotPrice(lots)
        self.__spotCost[coinId] = [{'amount': coinAmount, 'price': avgPrice}]
        return True

    def _avgSpotPrice(self, lots: list[dict]) -> float:
        totalAmount = sum(self._float(lot.get('amount')) for lot in lots)
        totalCost = sum(self._float(lot.get('amount')) * self._float(lot.get('price')) for lot in lots)
        if totalAmount:
            return totalCost / totalAmount
        return 0.0

    def _baseCoin(self, coinId: str) -> str:
        infoSymbol = coinId
        for quote in ('USDT', 'USDC', 'BUSD', 'FDUSD', 'BTC', 'ETH', 'BNB'):
            if infoSymbol.endswith(quote):
                return infoSymbol[:-len(quote)]
        return infoSymbol

    def _float(self, value: object) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
    

    # def position(self, exName: str = '') -> dict:
    #     if exName:
    #         return self._snapshot.get(exName, {}).get('position', {})
    #     return {ex: d.get('position', {}) for ex, d in self._snapshot.items()}

 

    # def _onPosition(self, exName: str, positions: list):
    #     pos = {p['symbol']: p for p in positions if float(p.get('contracts', 0)) != 0}
    #     prev = self._snapshot.setdefault(exName, {}).get('position', {})
    #     self._snapshot.setdefault(exName, {})['position'] = pos
    #     if pos != prev:
    #         import asyncio
    #         asyncio.ensure_future(
    #             evtFireAsync(kEvt_Market, eMarketId['iHolding'], exName, 'position', pos, prev)
    #         )
