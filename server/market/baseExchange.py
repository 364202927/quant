import ccxt
import pandas as pd
from server.market.consts import kSpot, kSwap, kFuture, kDelivery, kBuy, kSell, kShort,kLong,kMarket, kLimit
from server.utils import switch, switchFn, tryCatch, aContainB, slit, str2ms, pdData, err, log, inRange, utc_now, reviseTime, timeFrame2Float, diff_Pdtime, logFormat,trySwitchFn

class baseExchange:

    def __init__(self, description: str, maxLimit: int):
        self.__description = description
        self._maxLimit = maxLimit
        self._ccxt = None
        self._title = ''
        self._id = ''
        self._info = {'acc': {}, 'coin': {}, 'api': {}}

    def get(self, key: str):
        return switch({
            'id': self.__class__.__name__,
            'des': self.__description,
            'title':self._title,
            'ccxt': self._ccxt,
            'acc': self._info['acc'],
            'coinInfo': self._info['coin']}, key=key)

    def enroll(self, config: dict,title:str):
        self._create(config)
        self._title = title
        self._utc = utc_now()

    def showApi(self):
        print("ccxt版本：", ccxt.__version__, "public/private + get/post + path, 驼峰编码")
        print("~~~~ccxt私有~~~~~\n", dir(self._ccxt))
        print('\n~~~~支持信息~~~~~~\n', self._ccxt.has)

    #账户信息
    def account(self) -> dict:
        info = self._ccxt.fetch_balance()
        self._info['acc'] = {
            'total': {coin: amount for coin, amount in info['total'].items() if amount > 0},
            'used': {coin: amount for coin, amount in info['used'].items() if amount > 0},
            'free': {coin: amount for coin, amount in info['free'].items() if amount > 0}}
        return self._info['acc']

    #余额查询
    def accFree(self, isSpot: bool = False, coin: str = ''):
        account = self.get("acc")
        # print("~~~~~accFree~~~~~~",account)
        if isSpot:
            amt = float(account['free'].get('USDT', 0))
            if coin == 'all':return account['free']
            if coin != '':
                amt = account['free'].get(coin) or 0
            return amt
        return self._accPm(account, coin)

    #当前交易所的所有币种
    def markets(self, reset: bool = False) -> dict:
        kSymbol = 'coin'
        if not reset and self._info.get(kSymbol):
            return self._info[kSymbol]
        self._info[kSymbol] = {kSpot: {}, kSwap: {}, kFuture: {}, kDelivery: {}}
        markets = self._ccxt.loadMarkets()
        for symbol, market in markets.items():
            if market['active']:
                self._info[kSymbol][market['type']][symbol] = {
                    'id': market['id'],
                    'symbol':symbol,
                    'step':market['precision']['amount'],
                    'market': market['limits']['market'],
                    'amount': market['limits']['amount'],   #币个数
                    'price': market['limits']['price'],
                    'cost': market['limits']['cost']}
        return self._info[kSymbol]

    # 获取币信息
    def coinInfo(self, symbol: str) -> tuple:
        category, newSymbol = slit(symbol, '_')
        def _find():
            res = slit(newSymbol, '-')
            sel = 0
            futureSymbol = newSymbol if res == False else res[0]
            # print("~~~res~~~~~~",res, futureSymbol)# ,market.get(category))
            # 过滤出同一基础合约的所有到期/交割键，按日期后缀排序后选择目标键
            keys = [market.get(category).get(futureSymbol)]
            # print("~~~keys~~~~",keys)
            if keys[0]== None:
                keys = [k for k in market.get(category).keys() if k.split(':')[0] == futureSymbol]
                if not keys:
                    return category, None
                keys.sort(key=lambda k: k.split('-')[-1])
                sel = int(res[1])
            # print("~~~~~~~all~~~~~~~~", keys, sel)
            # target_key = keys[sel]
            return market.get(category).get(keys[sel])
        #
        market = self.get("coinInfo")
        info = switchFn({kDelivery: _find,
                        kFuture: _find,
                        'default': lambda: market.get(category).get(newSymbol)
                        }, key=category)
        # print("~~~~~info2~~~~",newSymbol, market.get(category).get(newSymbol))
        # if info:
        return category, info
        # return None

    #symbol: 交易对,seTime: [开始时间, 结束时间],timeframe: K线周期,limit: 单次获取数量，0表示使用交易所最大值
    def getKline(self, symbol: str, seTime: list, timeframe: str = '5m', limit: int = 0):
        dateFrame = self._marketKline(symbol, seTime, timeframe, limit)
        lastTime = dateFrame.iloc[-1].candle_begin_time
        timeInterval = timeFrame2Float(timeframe)
        if len(seTime) < 2 or \
            diff_Pdtime(lastTime, seTime[1]) < timeInterval:
            return dateFrame
        end = pd.Timestamp(seTime[1])
        if lastTime >= end:
            return dateFrame
        # 按时间范围获取全部数据
        allData = [dateFrame]
        nextTime = lastTime
        endTime = pd.Timestamp(seTime[1])
        log(f"开始从交易所获取k线: {symbol}")
        while True:
            dateFrame = self._marketKline(symbol, [nextTime.strftime("%Y-%m-%d %H:%M:%S"), str(seTime[1])], timeframe, limit)
            nextTime = dateFrame.iloc[-1].candle_begin_time
            allData.append(dateFrame)
            print(f" 时间: {nextTime} ~ {endTime},跳出判断:{diff_Pdtime(nextTime, endTime)}<{timeInterval}")
            if diff_Pdtime(nextTime, endTime) <= timeInterval:
                break
        # 合并全部数据
        allpd = pdData()
        allpd.format(allData, style='concat')
        return allpd.get()

    #订单接口state:  'buy' | 'sell' | 'cancel'
    def order(self, state: str, symbol: str, totelPrice, amount: float, price: float | None = None, isMarket=False, inForce='GTC', posSide: str | None = None, lv: int = 1):
        category, symbolInfo = self.coinInfo(symbol)
        kwargs = {'state': state, 'symbol': symbolInfo['id']}
        isSpot = category == kSpot
        def _validateOrderParams(symbolInfo: dict):
            if amount and not inRange([symbolInfo['amount'].get('min'), symbolInfo['amount'].get('max')], amount):
                print(symbol, ":amount取值范围为:", symbolInfo['amount'])
                return False
            if price and not inRange([symbolInfo['price'].get('min'), symbolInfo['price'].get('max')], price):
                print(symbol, ":price取值范围为:", symbolInfo['price'])
                return False
            totle = amount * price if amount and price else totelPrice
            if not inRange([symbolInfo['cost'].get('min'), symbolInfo['cost'].get('max')], totle):
                print(symbol, ":总下单金额范围:", symbolInfo['cost'], '当前价格:', totle)
                return False
            return True
        #参数调整
        def _setkWargs():
            nonlocal kwargs
            kwargs.update(symbol=symbolInfo, totelPrice=totelPrice, amount=amount, price=price)
            if isSpot:
                return
            kwargs.update(symbol=symbol, lv=lv, posSide=posSide, isMarket=isMarket, inForce=inForce)
            kwargs.pop('totelPrice', None)
        def _setCancel():
            nonlocal kwargs
            kwargs = {'id':totelPrice, 'symbol':symbolInfo.get('symbol')}
            # print("~~~~~~~~~~~~~~~~~~",kwargs)
            if isSpot:
                return
            kwargs['symbol'] = symbol
        #logic
        if state in (kBuy, kSell):
            if not _validateOrderParams(symbolInfo):
                return
        switchFn({
            # kFind: lambda kwargs:{'symbol':symbol,'orderId':totelPrice}, #
                    'cancel': _setCancel,
                    'default': _setkWargs
                }, key=state)
        
        return switchFn({
            # kFind: self._findOrder,#self._ccxt.fetchOrder if isSpot else self._findOrder,
                        kBuy: self._sporOrder if isSpot else self._contractOrder,
                        kSell: self._sporOrder if isSpot else self._contractOrder,
                        'cancel': self._ccxt.cancelOrder if isSpot else self._cancelOrder
                        }, key=state, **kwargs)
    #获取个人交易记录
    def trades(self, symbol: str, limit: int = 500) -> list[dict]:
        category, symbolInfo = self.coinInfo(symbol)
        if category == kSwap:
            return self._trades(symbol, limit)
        rt = tryCatch(lambda: self._ccxt.fetch_my_trades(symbolInfo['symbol'], limit=limit))
        if not rt:
            return []
        return [self._formatTrade(t) for t in rt]

    #批量下单
    def batchOrders(self, category: str, orders: list[dict]) -> list:
        if not orders or len(orders) > 5:
            err("batchOrders: 订单数量需在1-5之间")
            return []
        return self._batchOrders(category, orders)

    # 子类可继承接口
    def _create(self, config: dict):
        self._info['api'] = {'apiKey': config['apiKey'], 'secret': config['secret']}
    # def checkPosition(self, symbol, position): pass
    def orderBook(self, symbol: str, limit: int = 5): pass
    def depth(self, symbol, limit): pass
    def tickers(self, symbol): pass
    def findOrder(self, symbol: str, orderId: str = '',isPos = True,isOpen = False): pass 
    def _accPm(self, account, coin) -> float: return 0
    def _contractOrder(self, state: str, symbol: dict, amount: float, isMarket, inForce, price: float | None = None, lv: int = 1, posSide: str | None = None): pass
    def _cancelOrder(self, symbol: str, id: str): pass
    def _batchOrders(self, category, orders): pass
    def _trades(self, symbol: str, limit: int = 500) -> list[dict]:pass
    def _formatCcxtOrder(self, rt: dict) -> dict:
        fee = rt.get('fee', {})
        return {
            'orderId': str(rt.get('id', '')),
            'symbol': rt.get('symbol', ''),
            'status': 'closed' if rt.get('status') == 'closed' else ('cancel' if rt.get('status') == 'canceled' else 'open'),
            'side': rt.get('side', ''),
            'positionSide': rt.get('info', {}).get('positionSide'),
            'origQty': float(rt.get('amount') or 0),
            'avgPrice': float(rt.get('average') or rt.get('price') or 0),
            'cumQuote': float(rt.get('cost') or 0),
            'fee': float(fee.get('cost') or 0) if fee else 0,
            'time': rt.get('timestamp') or 0,
            'updateTime': rt.get('lastUpdateTimestamp') or 0}

    def _formatTrade(self, t: dict) -> dict:
        fee = t.get('fee', {})
        info = t.get('info', {})
        return {
            'symbol': t.get('symbol', ''),
            'orderId': str(t.get('order', '')),
            'side': t.get('side', ''),
            'positionSide': info.get('positionSide', ''),
            'price': float(t.get('price') or 0),
            'qty': float(t.get('amount') or 0),
            'cost': float(t.get('cost') or 0),
            'fee': abs(float(fee.get('cost') or 0)) if fee else 0,
            'realizedPnl': float(info.get('realizedPnl') or 0),
            'time': t.get('timestamp') or 0}

    def _marketKline(self, symbol: str, seTime: list, timeframe: str = '5m', limit: int = 0):
        time = None
        if len(seTime) > 0:
            time = str2ms(seTime[0])
        return self._ccxt.fetch_ohlcv(symbol=symbol, timeframe=timeframe, since=time, limit=limit)

    def _sporOrder(self, state: str, symbol, totelPrice=None, amount=None, price=None):
        params = {'symbol': symbol.get('id'),
                  'side': state,
                  'type': kMarket,
                   'amount':None, 
                   'price':None,
                   'params':{'quoteOrderQty': totelPrice}}
        if amount and price:
            params.update(type=kLimit, amount=amount, price=price)
            del params['params']
        # if state == kSell:
        #     params['params']['reduceOnly'] = True

        # exit()
        rt = tryCatch(lambda: self._ccxt.create_order(**params))
        if not rt:
            return None
        return self._formatCcxtOrder(rt)
        
        #现货返回值
        # {'info': {'symbol': 'DOGEUSDT', 'orderId': '13856448896', 'orderListId': '-1', 'clientOrderId': 'x-TKT5PX2F583f2601e4dfe7ae40fac2', 'transactTime': '1771961066709', 'price': '0.00000000', 
        # 'origQty': '10.00000000', 'executedQty': '10.00000000', 'origQuoteOrderQty': '1.00000000', 'cummuulativeQuoteQty': '0.91830000', 'status': 'FILLED', 'timeInForce': 'GTC', 'type': 'MARKET', 'side': 'BUY', 'workingTime': '1771961066709', 
        # 'fills': [{'price': '0.09183000', 'qty': '10.00000000', 'commission': '0.00000117', 'commissionAsset': 'BNB', 'tradeId': '1485337765'}], 'selfTradePreventionMode': 'EXPIRE_MAKER'}, 
        # 'id': '13856448896', 'clientOrderId': 'x-TKT5PX2F583f2601e4dfe7ae40fac2', 'timestamp': 1771961066709, 'datetime': '2026-02-24T19:24:26.709Z', 'lastTradeTimestamp': 1771961066709, 
        # 'lastUpdateTimestamp': 1771961066709, 'symbol': 'DOGE/USDT', 'type': 'market', 'timeInForce': 'GTC', 'postOnly': False, 'reduceOnly': None, 'side': 'buy', 'price': 0.09183, 'triggerPrice': None, 
        # 'amount': 10.0, 'cost': 0.9183, 'average': 0.09183, 'filled': 10.0, 'remaining': 0.0, 'status': 'closed', 
        # 'fee': {'currency': 'BNB', 'cost': 1.17e-06}, 
        # 'trades': [{'info': {'price': '0.09183000', 'qty': '10.00000000', 'commission': '0.00000117', 'commissionAsset': 'BNB', 'tradeId': '1485337765'}, 
        # 'timestamp': None, 'datetime': None, 'symbol': 'DOGE/USDT', 'id': '1485337765', 'order': None, 'type': None, 'side': None, 'takerOrMaker': None, 
        # 'price': 0.09183, 'amount': 10.0, 'cost': 0.9183, 'fee': {'currency': 'BNB', 'cost': 1.17e-06}, 
        # 'fees': [{'currency': 'BNB', 'cost': 1.17e-06}]}], 'fees': [{'currency': 'BNB', 'cost': 1.17e-06}], 
        # 'stopPrice': None, 'takeProfitPrice': None, 'stopLossPrice': None}
        #挂单
        # {'symbol': 'DOGEUSDT', 'side': 'BUY', 'executedQty': '0', 'orderId': '93887302283', 'goodTillDate': '0', 'avgPrice': '0.000000', 'origQty': '72', 'clientOrderId': 'kCQ039jj39sYlllzsjy186', 'positionSide': 'LONG', 'cumQty': '0', 'updateTime': '1772028578356', 'type': 'LIMIT', 'reduceOnly': False, 'price': '0.070000', 'cumQuote': '0.000000', 'selfTradePreventionMode': 'EXPIRE_MAKER', 'timeInForce': 'GTC', 'status': 'NEW', 'priceMatch': 'NONE'}
        # {'symbol': 'ETHUSDT_260327', 'side': 'BUY', 'executedQty': '0.000', 'orderId': '1245346799', 'goodTillDate': '0', 'avgPrice': '0.00000', 'origQty': '0.004', 'clientOrderId': 'lZK7HYPb8TeYfdBvY5s57', 'positionSide': 'LONG', 'cumQty': '0.000', 'updateTime': '1772039694055', 'type': 'LIMIT', 'reduceOnly': False, 'price': '1500.00', 'cumQuote': '0.00000', 'selfTradePreventionMode': 'EXPIRE_MAKER', 'timeInForce': 'GTC', 'status': 'NEW', 'priceMatch': 'NONE'}