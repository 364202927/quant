from server.utils import kEvt_Market, slit,evtReturn
from server.market import eMarketId, kSpot, kSell, kSwap,kBuy, kCancel,kClose,kLong,kShort,baseExchange

#todo:检测策略连续亏损,风格等
#todo:价格偏离


class preTrade:
    "开仓/买入(风控检测)：限额/价格偏离/黑名单。由 gateway 流水线直接调用,不挂事件总线"

    def __init__(self):
        pass

    # 通过返回True,拦截返回原因字符串
    def check(self, data: dict, ex:baseExchange):
        orderType = data.get('type', '')
        #暂时只支持现货和合约
        if orderType == kCancel:
            return True
        if orderType not in (kSpot, kSwap):
            return f"不支持的下单类型: {orderType}, 仅支持 {kSpot}/{kSwap}"

        symbol = data.get('symbol', '')
        direction = data.get('dir', '')
        totelPrice = data.get('totelPrice', 0)
        splitSymbol = slit(symbol, '_')
        newSymbol = splitSymbol[1] if splitSymbol else symbol
        _, symbolInfo = ex.coinInfo(data['symbol'])
        if not symbolInfo:
            return  f"无法获取币种信息: {data['symbol']}"
        # a. passList 过滤
        symbol_lower = symbol.lower()
        if not any(p in symbol_lower for p in self._passList()):
            return  f"symbol {symbol} 不在 passList 中"

        splitBase = slit(newSymbol, "/")
        baseCoin = splitBase[0] if splitBase else newSymbol
        quoteCoin = splitBase[1].split(":")[0] if splitBase else 'USDT'

        def _bet2Value(value) -> float:
            if isinstance(totelPrice, str) and totelPrice.startswith('bet:'):
                return float(totelPrice[4:]) * 0.01 * value
            return float(totelPrice or 0)

        def _checkOpenBalance(coin: str, isPm: bool, actionLabel: str, assetLabel: str):
            assets = ex.accFree(coin=coin, isPm=isPm)
            total = _bet2Value(assets)
            coinMin = symbolInfo['cost'].get('min')
            total = coinMin if coinMin > total else total
            if total > assets:
                return f"{actionLabel}金额不足: {total}, {assetLabel}: {assets}"
            data['consumeCoin'] = coin
            data['totelPrice'] = total
            return None

        if orderType == kSpot and direction == kBuy:
            reason = _checkOpenBalance(quoteCoin, False, "现货买入", f"{quoteCoin}余额")
            if reason:
                return reason

        elif orderType == kSpot and direction == kSell:
            assets = ex.accFree(coin=baseCoin, isPm=False)
            if isinstance(totelPrice, str) and totelPrice.startswith('bet:'):
                if assets <= 0:
                    return f"现货卖出余额不足: {baseCoin}余额: {assets}"
            else:
                orderValue = float(totelPrice or 0)
                if orderValue <= 0:
                    return f"现货卖出金额无效: {totelPrice}"
            data['consumeCoin'] = baseCoin

        elif orderType == kSwap and direction in (kBuy, kSell):
            reason = _checkOpenBalance(quoteCoin, True, "合约开仓", "可用")
            if reason:
                return reason

        elif orderType == kSwap and direction == kClose:
            taskName = data.get('taskName', '')
            querySymbol = symbolInfo.get('id')
            positions = evtReturn(kEvt_Market, 'storageOrders', eMarketId['gPosit'], 'task', querySymbol, taskName)
            taskPositions = positions.get(taskName, []) if isinstance(positions, dict) else []
            matched = self._matchTaskPosition(taskPositions, data.get('posSide'))
            if not matched:
                return f"未找到task可平仓位: {symbol} {data.get('posSide')}"
            data['consumeCoin'] = quoteCoin
        else:
            return f"不支持的方向: {orderType}/{direction}"
        
        #赋值给oms
        data['coinInfo'] = symbolInfo
        return True

    def _matchTaskPosition(self, positions: list[dict], posSide: str | None) -> bool:
        if posSide in ('all', '', None):
            return bool(positions)
        if posSide == kLong:
            target = 'long'
        elif posSide == kShort:
            target = 'short'
        else:
            target = posSide.lower()
        return any(item.get('dir') == target for item in positions)

    def _passList(self) -> list[str]:
        return ['btc', 'eth', 'doge']  # symbol 含有此字段才能通关