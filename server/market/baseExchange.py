import ccxt
import time
import pandas as pd
from server.utils import switch, switchFn, tryCatch, aContainB, slit, str2ms, pdData, err, log, inRange, utc_now, reviseTime, timeFrame2Float,diff_Pdtime,logFormat

kFilter = []#["BTC/USDT", "ETH/USDT", "BNB/USDT", "OKB/USDT", "DOGE/USDT", "USDC/USDT"]
kSpot, kSwap = 'spot', 'swap'
kBuy, kSell, kFind = 'buy', 'sell', 'find'
kMarket, kLimit = 'MARKET', 'LIMIT'
kUm, kCm, kEo = 'um', 'cm', 'eo'  # U本位、币本位、期权

class baseExchange:

    def __init__(self, description: str, maxLimit: int):
        self.__description = description
        self._maxLimit = maxLimit
        self._ccxt = None
        self._id = ''
        self._info = {}

    # def name(self) -> str:
    #     return self.__class__.__name__

    def get(self, key: str):
        return switch({
            'id': self.__class__.__name__,
            'des': self.__description,
            'ccxt': self._ccxt,
            'acc': self._info['acc'],
            'coinInfo': self._info['coin']}, key=key)

    def enroll(self, config: dict):
        self.create(config)
        self._utc = utc_now()

    def create(self, config: dict):
        exchangeClass = getattr(ccxt, type(self).__name__)
        self._ccxt = exchangeClass({
            'apiKey': config['apiKey'],
            'secret': config['secret'],
            'timeout': 3000,
            'enableRateLimit': True})

    def showApi(self):
        print("ccxt版本：", ccxt.__version__, "public/private + get/post + path, 驼峰编码")
        print("~~~~ccxt私有~~~~~\n", dir(self._ccxt))
        print('\n~~~~支持信息~~~~~~\n', self._ccxt.has)

    #账户信息
    def account(self) -> dict:
        info = self._ccxt.fetch_balance()
        self._info['acc'] = {
            'total': info['total'],
            'used': info['used'],
            'free': info['free']}
        return self._info['acc']

    def accFree(self, isSpot: bool = False) -> float:
        """返回账户可用余额"""
        account = self.get("acc")
        if isSpot:
            return float(account['free']['USDT'])
        return float(self._accFutures(account))

    def markets(self, reset: bool = False) -> dict:
        if not reset and self._info.get('coin'):
            return self._info['coin']

        self._info['coin'] = {}
        markets = self._ccxt.loadMarkets()
        for symbol, market in markets.items():
            if market['active']:#aContainB(symbol, kFilter) and market['active']:
                # self._info['coin'][symbol] = {
                #     'id': market['id'],
                #     # 'pair': market['info'].get('pair'),
                #     'type': market['type'],
                #     'amount': market['limits']['amount'],
                #     'price': market['limits']['price'],
                #     'cost': market['limits']['cost']}
                if not self._info['coin'][market['type']]:
                    self._info['coin'][market['type']] = {}
                self._info['coin'][market['type']][symbol]= {
                    'id': market['id'],
                    'amount': market['limits']['amount'],
                    'price': market['limits']['price'],
                    'cost': market['limits']['cost']}
        return self._info['coin']

    def coinInfo(self, symbol: str) -> tuple:
        """解析 symbol 返回 (category, symbolInfo)"""
        category, newSymbol = slit(symbol, '_')
        market = self.get("coinInfo")
        info = market.get(newSymbol)
        if info:
            return category, info
        return category, newSymbol

    #symbol: 交易对,seTime: [开始时间, 结束时间],timeframe: K线周期,limit: 单次获取数量，0表示使用交易所最大值
    def getKline(self, symbol: str, seTime: list, timeframe: str = '5m', limit: int = 0):
        dateFrame = self._marketKline(symbol, seTime, timeframe, limit)
        lastTime = dateFrame.iloc[-1].candle_begin_time
        # 没有结束时间或者是最新的时间则返回
        timeInterval = timeFrame2Float(timeframe)
        if len(seTime) < 2 or \
            diff_Pdtime(lastTime, seTime[1]) < timeInterval:
            return dateFrame
        end = pd.Timestamp(seTime[1])
        if lastTime >= end:
            # print("~~~~异常~~~~~~~",lastTime.strftime("%Y-%m-%d %H:%M:%S"),end.strftime("%Y-%m-%d %H:%M:%S"))
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
            time.sleep(0.1)
        # 合并全部数据
        allpd = pdData()
        allpd.format(allData, style='concat')
        return allpd.get()

    def order(self, state: str, **kwargs):
        """
        统一订单接口
        state: 'find' | 'buy' | 'sell' | 'cancel'
        """
        category, symbolInfo = self.coinInfo(kwargs['symbol'])
        kwargs['symbol'] = symbolInfo['id']

        if state in (kBuy, kSell):
            self._validateOrderParams(symbolInfo, kwargs)

        if state in (kBuy, kSell) or (state == 'cancel' and category == kSwap):
            kwargs['state'] = state
            if state == 'cancel':
                kwargs['symbol'] = symbolInfo['id']
            else:
                kwargs['symbol'] = symbolInfo

        isSpot = (category == kSpot)
        handlers = {
            kFind: self._ccxt.fetchOrder if isSpot else self._futureFind,
            kBuy: self._sporOrder if isSpot else self._futureOrder,
            kSell: self._sporOrder if isSpot else self._futureOrder,
            'cancel': self._ccxt.cancelOrder if isSpot else self._futureCancal
        }
        return switchFn(handlers, key=state, **kwargs)

    def _validateOrderParams(self, symbolInfo: dict, kwargs: dict):
        """校验订单参数范围"""
        symbol = kwargs.get('symbol', '')
        amount = kwargs.get('amount')
        price = kwargs.get('price')

        amountRange = [symbolInfo['amount'].get('min'), symbolInfo['amount'].get('max')]
        if not inRange(amountRange, amount):
            err(symbol, ":amount取值范围为:", symbolInfo['amount'])

        if price:
            priceRange = [symbolInfo['price'].get('min'), symbolInfo['price'].get('max')]
            if not inRange(priceRange, price):
                err(symbol, ":price取值范围为:", symbolInfo['price'])

            costRange = [symbolInfo['cost'].get('min'), symbolInfo['cost'].get('max')]
            if not inRange(costRange, price * amount):
                err(symbol, ":总下单金额范围:", symbolInfo['cost'])

    def batchOrders(self, category: str, orders: list[dict]) -> list:
        """批量下单，最多5单"""
        if not orders or len(orders) > 5:
            err("batchOrders: 订单数量需在1-5之间")
            return []
        return self._batchOrders(category, orders)

    # 子类需实现的接口
    def checkPosition(self, symbol, position): pass
    def bookTickers(self, symbol): pass
    def depth(self, symbol, limit): pass
    def trades(self, symbol, limit): pass
    def tickers(self, symbol): pass
    def _accFutures(self, account) -> float: return 0
    def _futureFind(self, **kwargs): pass
    def _futureOrder(self, **kwargs): pass
    def _futureCancal(self, **kwargs): pass
    def _batchOrders(self, category, orders): pass
    def _marketKline(self, symbol: str, seTime: list, timeframe: str = '5m', limit: int = 0):
        # effectiveLimit = limit if limit > 0 else self._maxLimit
        time = None
        if len(seTime) > 0 :
            time = str2ms(seTime[0])
        return self._ccxt.fetch_ohlcv(symbol=symbol,timeframe=timeframe,since=time,limit=limit)

    def _sporOrder(self, **kwargs):
        state = kwargs['state']
        symbol = kwargs['symbol'].get('id')
        amount = kwargs.get('amount')
        price = kwargs.get('price')
        orderType = 'limit' if price else 'market'

        rt = tryCatch(lambda: self._ccxt.create_order(symbol, orderType, state, amount, price))
        if not rt:
            return None

        rt['orderId'] = rt['info'].get('orderId')
        if rt.get('trades'):
            rt['fee'] = rt['trades'][0]['info'].get('commission')
        return rt