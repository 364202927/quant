import ccxt
from server.utils import (switch,switchFn,tryExecution,aContainB,slit,str2ms,g_config,pdData,err,inRange,utc_now)
kFilter = [ "BTC/USDT", "ETH/USDT", "BNB/USDT", "OKB/USDT", "DOGE/USDT", "USDC/USDT" ]
kSpot,kSwap = 'spot','swap'
kBuy,kSell,kFind = 'buy','sell','find'

class baseExchange:
    def __init__(self, description, maxLimit):
        self.__description = description
        self._maxLimit = maxLimit
        self._ccxt = None
        self._id = ''
        self._info = {}

    def name(self):
        return self.__class__.__name__  # type(self).__name__

    def get(self, key):
        return switch({
            'id': self._id,
            'des': self.__description,
            'ccxt': self._ccxt,
            'acc': self._info['acc'],  # 交易所账号信息
            'coinInfo': self._info['coin']  # 交易所支持的币种
        }, key=key)

    # 注册
    def enroll(self, config):
        self.create(config)
        # self.markets()     todo:先去掉
        self._utc = utc_now()
        # 获取支持信息
        # self._ccxt.has

    def create(self, config):
        exchangeClass = getattr(ccxt, type(self).__name__)
        self._ccxt = exchangeClass({
            'apiKey': config['apiKey'],
            'secret': config['secret'],
            'timeout': 3000,
            'enableRateLimit': True})

    # 返回能使用的api
    def showApi(self):
        print("ccxt版本：",ccxt.__version__,"public/private + get/post + path, 驼峰编码")
        # print("~~~~ccxt私有~~~~~", *list(dir(self._ccxt)), sep='\n')
        print("~~~~ccxt私有~~~~~\n", dir(self._ccxt))
        print('\n~~~~支持信息~~~~~~\n', self._ccxt.has)
        # logFormat(self._ccxt.has)

    # 账号数据
    def account(self):
        info = self._ccxt.fetch_balance()
        self._info['acc'] = {
            'total': info['total'],
            'used': info['used'],
            'free': info['free']}
        return self._info['acc']

    # 返回账号可用的钱
    def accFree(self, isSpot=False):
        account = self.get("acc")
        if isSpot:
            return float(account['free']['USDT'])
        return float(self._accFutures(account))

    # 获取市场全种类信息
    def markets(self, reset=False):
        if not reset and self._info.get('coin') and len(self._info['coin']) > 0:
            return self._info['coin']
        # init
        self._info['coin'] = {}
        market = self._ccxt.loadMarkets()
        for symbol, market in market.items():
            if aContainB(symbol, kFilter) and market['active']:
                self._info['coin'][symbol] = {
                    'id': market['id'],
                    'pair': market['info'].get('pair'),
                    'type': market['type'],
                    'amount': market['limits']['amount'],
                    'price': market['limits']['price'],
                    'cost': market['limits']['cost']  # 最少下单金额
                }
        return self._info['coin']

    def coinInfo(self, symbol):
        category, newSymbol = slit(symbol, '_')
        market = self.get("coinInfo")
        if market.get(newSymbol):
            return category, market.get(newSymbol)
        return category, newSymbol

    # 获取一段时间的k线，limit默认应该是交易所最大值
    def getKline(self, symbol, seTime, timeframe='5m', limit=0):
        kLineData = self._ccxt.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            since=str2ms(seTime[0]),
            limit=limit == 0 and self._maxLimit or limit)
        return kLineData

    # 订单
    # 必要参 state
    # 查单 find(symbol, id)
    # 买入/卖出 buy|sell  现货(symbol, amount, price)   u本位(symbol, side, positionSide, price, amount)
    # 取消挂单 cancel(symbol, orderId)
    def order(self, state, **kwargs):
        category, symbolInfo = self.coinInfo(kwargs['symbol'])
        kwargs['symbol'] = symbolInfo['id']
        if state == kBuy or state == 'sell':
            if not inRange([symbolInfo['amount'].get('min'), symbolInfo['amount'].get('max')],kwargs['amount']):
                err(kwargs['symbol'], ":amount取值范围为:", symbolInfo['amount'])
            if kwargs.get('price'):
                if not inRange([symbolInfo['price'].get('min'), symbolInfo['price'].get('max')], kwargs['price']):
                    err(kwargs['symbol'], ":price取值范围为:", symbolInfo['price'])
                if not inRange([symbolInfo['cost'].get('min'), symbolInfo['cost'].get('max')], kwargs['price'] * kwargs['amount']):
                    err(kwargs['symbol'], ":总下单金额范围:", symbolInfo['cost'])
        if ((state == kBuy or state == kSell) or
                (state == 'cancel' and category == 'swap')):
            kwargs['state'] = state
            kwargs['symbol'] = (state == 'cancel' and symbolInfo['id'] or symbolInfo)
        # logic
        info = switchFn({
            kFind: (category == kSpot and self._ccxt.fetchOrder or self._futureFind),
            kBuy: (category == kSpot and self._sporOrder or self._futureOrder),
            kSell: (category == kSpot and self._sporOrder or self._futureOrder),
            'cancel': (category == kSpot and self._ccxt.cancelOrder or self._futureCancal)}, 
                key=state, attempts=1, **kwargs)
        return info

    #继承
    def checkPosition(self, symbol, position): pass  # 查询持仓
    def bookTickers(self, symbol):pass          # 订单本最优价
    def depth(self, symbol, limit):pass         # 深度数据 
    def trades(self, symbol, limit):pass        # 成交历史
    def tickers(self, symbol):pass              # 获取当前最新
    def _accFutures(self, account): return 0
    def _futureFind(self, **kwargs):pass
    def _futureOrder(self, **kwargs):pass
    def _futureCancal(self, **kwargs):pass

    def _sporOrder(self, **kwargs):
        state = kwargs['state']
        # params = {'symbol': kwargs['symbol'].get('id'),
        #         'amount': kwargs.get('amount'),
        #         'price': kwargs.get('price')}
        # rt = switchFn({
        #     'buy': (kwargs.get('price') and
        #             self._ccxt.createLimitBuyOrder or
        #             self._ccxt.createMarketBuyOrder),
        #     'sell': (kwargs.get('price') and
        #              self._ccxt.createLimitSellOrder or
        #              self._ccxt.createMarketSellOrder)
        # }, key=state, **params)
        # 市价买单
        rt = self._ccxt.create_order(
            kwargs['symbol'].get('id'),
            'market',
            state,
            kwargs.get('amount'))
        rt["orderId"] = rt['info']['orderId']
        rt['fee_Bnb'] = rt['trades'][0]['info'].get('commission')  # 手续费
        return rt