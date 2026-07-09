from server.utils import evtConnect, kEvt_Market, log, switchFn, slit, inRange,warn,evtFire
from server.market import eMarketId, kSpot, kSell, kSwap,kBuy, kCancel,kClose,baseExchange

#todo:检测策略连续亏损,风格等
#todo:价格偏离

class preTrade:
    "开仓/买入(风控检测)：限额/价格偏离/黑名单，通过则转发 oms"

    def __init__(self, exFn):
        self._getEx = exFn           # self._getEx(exname) 可获得对应 baseExchange
        evtConnect(kEvt_Market, self)

    def evtProcess(self, key, *args):
        id_, data= args[0],args[1] if len(args) > 1 else {}
        def _preTrade():
            exName = data.get('exName', '')
            ex = self._getEx(exName)
            if not ex:
                warn(f"[preTrade] 未找到交易所: {exName}")
                return
            reason = self._check(data, ex)
            if isinstance(reason,str):
                warn(f"[preTrade] 拦截: {reason}")
                return
            evtFire(kEvt_Market, eMarketId['oms'], data)
        switchFn({eMarketId['preTrade']: _preTrade}, key=id_)

    def _check(self, data: dict, ex:baseExchange):
        symbol = data.get('symbol', '')
        orderType = data.get('type', '')
        direction = data.get('dir', '')
        totelPrice = data.get('totelPrice', 0)
        splitSymbol = slit(symbol, '_')
        newSymbol = splitSymbol[1] if splitSymbol else symbol
        _, symbolInfo = ex.coinInfo(data['symbol'])
        isPm = (orderType == kSwap)
        def _bet2Value(value) -> float:
            if isinstance(totelPrice, str) and totelPrice.startswith('bet:'):
                return float(totelPrice[4:]) * 0.01 * value
            return float(totelPrice or 0)
        #暂时只支持现货和合约
        if orderType == kCancel:
            return True
        if orderType not in (kSpot, kSwap):
            return f"不支持的下单类型: {orderType}, 仅支持 {kSpot}/{kSwap}"
        if not symbolInfo:
            return  f"无法获取币种信息: {data['symbol']}"
        # a. passList 过滤
        symbol_lower = symbol.lower()
        if not any(p in symbol_lower for p in self._passList()):
            return  f"symbol {symbol} 不在 passList 中"
        
        baseCoin = slit(newSymbol, "/")[0]
        quoteCoin = slit(newSymbol, "/")[1].split(":")[0] if slit(newSymbol, "/") else 'USDT'

        if orderType == kSpot and direction == kBuy:
            assets = ex.accFree(coin=quoteCoin, isPm=False)
            total = _bet2Value(assets)
            coinMin = symbolInfo['cost'].get('min')
            total = coinMin > total and coinMin or total
            if total > assets:
                return f"现货买入金额不足: {total}, {quoteCoin}余额: {assets}"
            data['consumeCoin'] = quoteCoin
            data['totelPrice'] = total

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
            assets = ex.accFree(coin=quoteCoin, isPm=True)
            total = _bet2Value(assets)
            coinMin = symbolInfo['cost'].get('min')
            total = coinMin > total and coinMin or total
            if total > assets:
                return f"合约开仓金额不足: {total}, 可用: {assets}"
            data['consumeCoin'] = quoteCoin
            data['totelPrice'] = total

        elif orderType == kSwap and direction == kClose:
            positions = evtFire(kEvt_Market, eMarketId['gPosit'], 'ex', symbolInfo.get('id'), data.get('exName'))
            if not positions or data.get('exName') not in positions:
                positions = self._exchangePositions(ex, symbol, data.get('exName', ''))
            if not positions or data.get('exName') not in positions:
                return f"未找到可平仓位: {symbol}"
            data['consumeCoin'] = quoteCoin
            data['_positions'] = positions[data.get('exName')]
        else:
            return f"不支持的方向: {orderType}/{direction}"
        
        #赋值给oms
        data['coinInfo'] = symbolInfo
        return True

    def _passList(self) -> list[str]:
        return ['btc', 'eth', 'doge']  # symbol 含有此字段才能通关

    def _exchangePositions(self, ex: baseExchange, symbol: str, exName: str) -> dict:
        try:
            _, positions = ex.findOrder(symbol=symbol, isPos=True, isOpen=False)
        except Exception as e:
            warn(f"[preTrade] 查询持仓失败: {symbol} @ {exName}: {e}")
            return {}
        return {exName: positions} if positions else {}
