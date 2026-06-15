from server.utils import evtConnect, kEvt_Market, log, switchFn, slit, inRange,warn,evtFire
from server.market import eMarketId, kSpot, kSell, kSwap,kBuy, kCancel,baseExchange

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
        price = data.get('price')
        amount = data.get('amount')
        _, newSymbol = slit(symbol, '_')
        _, symbolInfo = ex.coinInfo(data['symbol'])
        isPm = (orderType == kSwap)
        def _bet2U(freeFunds) -> float: # bet转换成u
            if isinstance(totelPrice, str) and totelPrice.startswith('bet:'):
                proportion = float(totelPrice[4:]) * 0.01
                return proportion * freeFunds
            return totelPrice
        #暂时只支持现货和合约
        if orderType not in (kSpot, kSwap):
            return f"不支持的下单类型: {orderType}, 仅支持 {kSpot}/{kSwap}"
        if not symbolInfo:
            return  f"无法获取币种信息: {data['symbol']}"
        # a. passList 过滤
        symbol_lower = symbol.lower()
        if not any(p in symbol_lower for p in self._passList()):
            return  f"symbol {symbol} 不在 passList 中"
        
        # b. 仓位检测
        
        # 'type': kSpot//kSwap类型
        # 'dir': kBuy/kSell/close    方向
        # 1.现货
        # type:kSpot
        # dir:kBuy/kSell
        # 2.合约
        # type:kSwap
        # dir': kBuy/kSell/close
        # self, coin: str = 'USDT', isPm: bool = False
        coin = 'USDT' if (isPm == False and direction == kBuy) or (isPm == True and (direction==kBuy or direction== kSell)) else slit(newSymbol,"/")[0]
        assets = ex.accFree(coin= coin,isPm = isPm)
        totelPrice = _bet2U(assets)
        # if totelPrice > symbolInfo['cost'].get('max'): totelPrice = symbolInfo['cost'].get('max')
        # if isinstance(total, (int, float)) and not inRange(
        #     [symbolInfo['cost'].get('min'), symbolInfo['cost'].get('max')], total):
        #     return False, f"下单金额范围: {symbolInfo['cost']}, 当前: {total}"
        # print("~~~~~_check~~~~~~~",coin,assets,totelPrice)
        # 现货买/买合约开仓
        if coin == 'USDT':
            coinMin = symbolInfo['cost'].get('min') 
            totelPrice = coinMin > totelPrice and coinMin or totelPrice #下单金额必须 >min
            if totelPrice > assets:
                return f"下单金额不足: {totelPrice}, 余额: {assets}"
        else: #现货卖出/合约平仓
            pass
        

        # isClosePos = (direction == 'close') or \
        #              (category == kSpot and direction == kSell) #平仓检查

        # if not isClosePos:
        #     # 非平仓：检查账户余额
        #     freeMoney = ex.accFree(category == kSpot)
        #     if isinstance(totelPrice, str) and totelPrice.startswith('bet:'):
        #         # bet 格式暂不在此处转换（oms 处理），跳过余额检查
        #         pass
        #     elif isinstance(totelPrice, (int, float)) and totelPrice > freeMoney:
        #         return False, f"下单金额不足: {totelPrice}, 余额: {freeMoney}"
        # else:
        #     # 平仓检测
        #     if category == kSpot:
        #         coin = newSymbol.split('/')[0]
        #         accCoin = ex.accFree(category == kSpot, coin)
        #         if accCoin == 0:
        #             return False, f"现货账号 {coin} 不存在"

        # c. 参数校验（从 baseExchange._validateOrderParams 搬运）
        # if orderType == kCancel:
        #     return True, 'ok'  # 取消订单不校验价格/数量

        # if amount and not inRange(
        #     [symbolInfo['amount'].get('min'), symbolInfo['amount'].get('max')], amount):
        #     return False, f"amount 取值范围: {symbolInfo['amount']}, 当前: {amount}"

        # if price and not inRange(
        #     [symbolInfo['price'].get('min'), symbolInfo['price'].get('max')], price):
        #     return False, f"price 取值范围: {symbolInfo['price']}, 当前: {price}"
        
        
        #赋值给oms
        data['consumeCoin'] = coin
        data['totelPrice'] = totelPrice
        data['coinInfo'] = symbolInfo
        # data['ex'] = ex
        return True

    def _passList(self) -> list[str]:
        return ['btc', 'eth', 'doge']  # symbol 含有此字段才能通关
    
    # def _bet2U(self, ex: baseExchange, symbol: str, bet: str, isCoin: bool) -> float:
        # category, newSymbol = slit(symbol, '_')
        # coin = newSymbol.split('/')[0] if isCoin else ''
        # freeFunds = ex.accFree(category == kSpot, coin)
        # if bet.startswith("bet:"):
        #     proportion = int(bet[4:]) * 0.01
        #     return proportion * freeFunds
        # return 0.0
        # pass