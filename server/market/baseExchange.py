import ccxt
import time
from server.utils.common import (
    switch,
    trySwitchFn,
    tryExecution,
    aContainB,
    slit,
    str2ms,
    reviseTime,
    diff_Pdtime
)
from server.utils.fileConfig import g_config
from server.utils.pdData import pdData
from server.utils.logger import err
from server.utils.science import inRange

# todo优化方向:
# 1.冰山单
# 2.大单拆分         todo：暂时不需要
# 3.对冲现货         todo:暂时不需要
# 4.根据订单本下单
# 5.下单前先检测钱是否足够
# 6.下单绑定止损单(价格or止损单5%)


class baseExchange:
    __description = None  # 描述
    _maxLimit = 0  # 每个交易所不一样，最大页数据
    _utc = 0
    _ccxt = None
    _id = ''
    _info = {}  # 交易所 全币种信息
    _openOrders = []  # 未成交委托单

    def __init__(self, description, maxLimit):
        self.__description = description
        self._maxLimit = maxLimit
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
        self._utc = config['utc']
        # 获取支持信息
        # self._ccxt.has

    def create(self, config):
        exchangeClass = getattr(ccxt, type(self).__name__)
        self._ccxt = exchangeClass({
            'apiKey': config['apiKey'],
            'secret': config['secret'],
            'timeout': 3000,
            'enableRateLimit': True,
        })
        # balance = self._ccxt.fetch_balance()
        # print(balance)

    # 返回能使用的api
    def showApi(self):
        print(
            "ccxt版本：",
            ccxt.__version__,
            "public/private + get/post + path, 驼峰编码")
        # print("~~~~ccxt私有~~~~~", *list(dir(self._ccxt)), sep='\n')
        print("~~~~ccxt私有~~~~~\n", dir(self._ccxt))
        print('\n~~~~支持信息~~~~~~\n', self._ccxt.has)
        # logFormat(self._ccxt.has)

    # 账号数据
    def account(self):
        # rt = self._ccxt.fetch_balance()
        def balance():
            return self._ccxt.fetch_balance()

        rt, info = tryExecution(balance)
        self._info['acc'] = {
            'total': info['total'],
            'used': info['used'],
            'free': info['free']
        }
        return self._info['acc']

    # 返回账号可用的钱
    def accFree(self, isSpot=False):
        account = self.get("acc")
        if isSpot:
            return float(account['free']['USDT'])
        return float(self._accFutures(account))

    # 获取市场全种类信息
    def markets(self, reset=False):
        if not reset and self._info.get(
                'coin') and len(self._info['coin']) > 0:
            return self._info['coin']
        # init
        self._info['coin'] = {}
        market = self._ccxt.loadMarkets()
        for symbol, market in market.items():
            if aContainB(symbol, g_config.info("filter")) and market['active']:
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
            limit=limit == 0 and self._maxLimit or limit
        )
        return kLineData

    # 获取币种历史 (spot现货，swap永续，future期权) , [开始,结束时间], 时间粒度, 保存到文件
    def getHistoryCandles(self, symbol, seTime, timeframe='5m', fileType=""):
        pd = pdData()
        pf = self.getKline(symbol, seTime)
        pd.setPf(pf)
        allData = [pf]
        # 判断是否必要再获取
        diff_seconds = diff_Pdtime(pd.get(-1, 0))
        if diff_seconds < 5:
            return pd.get()

        print("开始从交易所获取k线")
        while 1:
            isSeq = pd.get(0, 0) < pd.get(-1, 0)
            startTime = isSeq and pd.get(-1, 0) or pd.get(0, 0)
            end = startTime
            pf = self.getKline(symbol, [str(startTime), str(seTime[1])])
            pd.setPf(pf)
            allData.append(pf)
            print(">>k线数量:", pf.shape[0], "  时间：",
                  end, "~", reviseTime(seTime[1], -10))
            if self._maxLimit > pf.shape[0] or end >= reviseTime(
                    seTime[1], -10):
                break
            time.sleep(0.1)
        pd.format(allData, style='concat')
        if fileType != "":  # 保存到文件
            pd.save2File(self.name() + "_" + symbol + fileType)
        if timeframe != '5m':  # 时间粒度
            pd.resample(timeframe)
        return pd.get()

    # 获取当前时间k线
    # def ticker(self, symbol, timeTs):
        # sconds = int(eTimeTs[timeTs])
        # preTime = reviseTime('now', -sconds)
        # return self.getKline(symbol, [preTime, 'now'], limit=1)
        # pass

    # todo:币当前价格， 修改u本位币本位
    # def tickerPrice(self, symbol):
    #     category, symbolInfo = self.coinInfo(symbol)
    # return self._ccxt.publicGetTickerPrice(params={'symbol':
    # symbolInfo.get('id')})

    # 订单
    # 必要参 state
    # 查单 find(symbol, id)
    # 买入/卖出 buy|sell  现货(symbol, amount, price)   u本位(symbol, side, positionSide, price, amount)
    # 取消挂单 cancel(symbol, orderId)
    def order(self, state, **kwargs):
        category, symbolInfo = self.coinInfo(kwargs['symbol'])
        kwargs['symbol'] = symbolInfo['id']
        if state == 'buy' or state == 'sell':
            if not inRange(
                [symbolInfo['amount'].get('min'), symbolInfo['amount'].get('max')],
                kwargs['amount']
            ):
                err(kwargs['symbol'], ":amount取值范围为:", symbolInfo['amount'])
            if kwargs.get('price'):
                if not inRange(
                    [symbolInfo['price'].get('min'), symbolInfo['price'].get('max')],
                    kwargs['price']
                ):
                    err(kwargs['symbol'], ":price取值范围为:", symbolInfo['price'])
                if not inRange(
                    [symbolInfo['cost'].get('min'), symbolInfo['cost'].get('max')],
                    kwargs['price'] * kwargs['amount']
                ):
                    err(kwargs['symbol'], ":总下单金额范围:", symbolInfo['cost'])
        if ((state == 'buy' or state == 'sell') or
                (state == 'cancel' and category == 'swap')):
            kwargs['state'] = state
            kwargs['symbol'] = (state == 'cancel' and symbolInfo['id'] or
                                symbolInfo)
        # logic
        rt, info = trySwitchFn({
            'find': (category == 'spot' and self._ccxt.fetchOrder or
                     self._futureFind),
            'buy': (category == 'spot' and self._sporOrder or
                    self._futureOrder),
            'sell': (category == 'spot' and self._sporOrder or
                     self._futureOrder),
            'cancel': (category == 'swap' and self._futureCancal or
                       self._ccxt.cancelOrder)
        }, key=state, attempts=1, **kwargs)
        if not rt:
            err('交易返回参数异常：', state, str(info))
            exit()
        return info

    # def allOrders(self):
    #     rt = self._ccxt.fapiprivateGetOpenorders(
    #         params={'timestamp': binanceTimestamp()}
    #     )
    #     print(rt)

    def checkPosition(self, symbol, position):
        pass

    def bookTickers(self, symbol):
        pass

    def depth(self, symbol, limit):
        pass

    def trades(self, symbol, limit):
        pass

    def tickers(self, symbol):  # 获取当前最新
        pass

    def _accFutures(self, account):
        return 0

    def _futureFind(self, **kwargs):
        pass

    def _futureOrder(self, **kwargs):
        pass

    def _futureCancal(self, **kwargs):
        pass

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
            kwargs.get('amount')
        )
        rt["orderId"] = rt['info']['orderId']
        rt['fee_Bnb'] = rt['trades'][0]['info'].get('commission')  # 手续费
        return rt
