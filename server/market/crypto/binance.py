import json
from server.market.baseExchange import *
from server.market import kPm
from server.utils import log, binanceTimestamp

kMaxLimit = 1000   # 现货最大 K 线
kfMaxLimit = 1500  # 合约最大


class BinancePAPI(ccxtpro.binance):
    #修复 ccxt.pro PAPI 账户资金键名混乱
    def handle_balance(self, client, message):
        self.balance.setdefault("papi", {})
        self.balance[""] = self.balance["papi"]
        super().handle_balance(client, message)
        self.balance["papi"] = self.balance.get("", self.balance["papi"])
        if client:
            snapshot = self.balance["papi"]
            for key in list(client.futures.keys()):
                if "balance" in key.lower():
                    client.resolve(snapshot, key)


class binance(baseExchange):
    '币安:只支持 现货/统一账号下的u本位'

    def __init__(self, description: str):
        super().__init__(description, kfMaxLimit)
        self._defaultLv: dict[str, int] = {}  # {symbol_id: leverage}
    
    def _create(self, config: dict):
        super()._create(config)
        api = self._info['api']
        proxy = 'socks5://127.0.0.1:10808'

        def _wsCreate(cls, **options):
            return cls({
                'apiKey':          api['apiKey'],
                'secret':          api['secret'],
                'socksProxy':      proxy,
                'wsSocksProxy':    proxy,
                'enableRateLimit': True,
                'timeout':         30000,
                'options':         options,
            })
        #ccxt
        self._ccxt = ccxt.binance({
            'apiKey':          api['apiKey'],
            'secret':          api['secret'],
            'timeout':         30000,
            'enableRateLimit': True,
            'options': {
                'adjustForTimeDifference': True,
                'recvWindow':  10000,
                'defaultType': kSpot,
            },
            'portfolioMargin': True,
            'proxies': {'http': proxy, 'https': proxy},
        })
        self._ccxt.load_time_difference()
        # ws
        self._ccxtSpot = _wsCreate(ccxtpro.binance, defaultType='spot')
        self._ccxtUm = _wsCreate(BinancePAPI, defaultType='papi', portfolioMargin=True)
        self._klineSpot = _wsCreate(ccxtpro.binance, defaultType='spot')
        self._klineUm = _wsCreate(ccxtpro.binance, defaultType='future')

    def _klineWsClient(self, category: str) -> ccxtpro.Exchange:
        client = self._klineSpot if category == kSpot else self._klineUm
        self._klineWs[category] = client
        return client

    #http取账号数据
    def balance(self, isSpot = True) -> dict:
        super().balance(isSpot)
        pmAcc = self._ccxt.sapiGetPortfolioAccount()
        pmCoin = self._ccxt.papi_get_balance()
        coin = {a: twb for item in pmCoin
                if (a := item['asset']) and (twb := float(item.get('totalWalletBalance', 0))) != 0}
		# 返回格式:{'total':{},'free':{},kPm:{}}
        self._acc[kPm] = {
            'equity': float(pmAcc['accountEquity']),
            'free': float(pmAcc['totalAvailableBalance']),
            'uniMMR': float(pmAcc['uniMMR']),
            'danger': float(pmAcc['accountMaintMargin']),
            'total': coin,
        }
        return self._acc

    def accFree(self, coin: str = '',isPm = False):
        if isPm:
            return self._acc[kPm].get('free') #联合账号可用金额
        return super().accFree(coin)

    def _orderParams(self, category: str) -> dict:
        if category in (kSwap, kFuture, kDelivery):
            return {'portfolioMargin': True}
        return {}

	# 订单查询
    def findOrder(self, symbol: str, orderId: str | int = '', isPos=True, isOpen=False):
        id, category = '', ''
        if symbol:
            category, symbolInfo = self.coinInfo(symbol)
            id = symbolInfo.get('id')
        targetId = str(orderId) if str(orderId) not in ('', '-1') else ''
        # 现货挂单
        if category == kSpot:
            open_orders = self._ccxt.fetch_open_orders(id)
            if targetId:
                open_orders = [o for o in open_orders
                               if str(o.get('id') or o.get('info', {}).get('orderId') or '') == targetId]
            return open_orders
        open_orders, pos_orders = [], []
        if isOpen:
            open_orders = self._ccxt.papi_get_um_openorders()
            if id:
                open_orders = [o for o in open_orders if o['symbol'] == id]
            if targetId:
                open_orders = [o for o in open_orders
                               if str(o.get('orderId') or o.get('id') or '') == targetId]
        if isPos:
            pos_orders = [{'symbol': o['symbol'],
                           'dir': (kBuy if float(o['positionAmt']) > 0 else kSell) + '_' + o['positionSide'],
                           'side': o['positionSide'],
                           'open': o['entryPrice'],
                           'lv': o['leverage'],
                           'unRealized': o['unRealizedProfit'],
                           'amount': abs(float(o['positionAmt']))}
                          for o in self._ccxt.papiGetUmPositionRisk()
                          if float(o['positionAmt']) != 0]
            if id:
                pos_orders = [p for p in pos_orders if p['symbol'] == id]
        if not isPos:
            return open_orders
        return open_orders, pos_orders
    # ── 合约下单 ──
    def _contractOrder(self, state: str, symbol: dict, amount: float, isMarket: bool, inForce: str, price: float | None = None, lv: int = 1, posSide: str | None = None, clientOrderId: str | None = None):
        category, symbolInfo = self.coinInfo(symbol)
        sid = symbolInfo.get('id')
        if self._defaultLv.get(sid) != lv:
            isUm = category in (kSwap, kFuture)
            lvApi = self._ccxt.papiPostUmLeverage if isUm else self._ccxt.papiPostCmLeverage
            lvApi(params={'symbol': sid, 'leverage': lv, 'timestamp': binanceTimestamp()})
            self._defaultLv[sid] = lv
        params = {
            'symbol': sid,
            'side': state.upper(),
            'positionSide': posSide,
            'quantity': amount,
            'type': kMarket if isMarket else kLimit}
        if not isMarket:
            params['price'] = price
            params['timeInForce'] = inForce
        if clientOrderId:
            params['newClientOrderId'] = clientOrderId
        return self._ccxt.papiPostUmOrder(params=params)

    # ── 合约撤单 ──
    def _cancelOrder(self, symbol: str, id: str):
        category, symbolInfo = self.coinInfo(symbol)
        sid = symbolInfo.get('id')
        if not id:
            return self._ccxt.papiDeleteUmAllOpenOrders(params={'symbol': sid, 'timestamp': binanceTimestamp()})
        return self._ccxt.papiDeleteUmOrder(params={'symbol': sid, 'orderId': id, 'timestamp': binanceTimestamp()})

    # ── 批量下单 ──
    def _batchOrders(self, category: str, orders: list[dict]):
        """批量下单，最多5单"""
        batchList = []
        for order in orders:
            isLimit = order.get('price') is not None
            item = {'symbol': order['symbol'],
                    'side': order['side'].upper(),
                    'positionSide': order['posSide'],
                    'quantity': str(order['amount']),
                    'type': kLimit if isLimit else kMarket}
            if isLimit:
                item['price'] = str(order['price'])
                item['timeInForce'] = order.get('timeInForce', 'GTC')
            batchList.append(item)

        params = {'batchOrders': json.dumps(batchList), 'timestamp': binanceTimestamp()}
        # 仅支持 PM 模式 u本位
        return tryCatch(lambda: self._ccxt.papiPostUmBatchOrders(params=params))

    # ── K线 ──
    def _marketKline(self, symbol: str, beginTime: int | None, endTime: int | None = None,
                     timeframe: str = '5m', limit: int = 0) -> pd.DataFrame | None:
        category, newSymbol = slit(symbol, '_')
        if category == kSpot:
            self._maxLimit = kMaxLimit
            kLineData = super()._marketKline(
                newSymbol, beginTime, endTime, timeframe=timeframe, limit=limit or self._maxLimit)
        elif category in (kSwap, kFuture, kDelivery):
            self._maxLimit = kfMaxLimit
            params = {'symbol': newSymbol,
                      'interval': timeframe,
                      'limit': limit or kfMaxLimit}
            if beginTime is not None:
                params['startTime'] = beginTime
            if endTime is not None:
                params['endTime'] = endTime
            kLineData = self._ccxt.fapiPublicGetKlines(params=params)
            if not kLineData:
                return None
        else:
            raise ValueError(f"未知的交易品种类型: {category!r} (symbol={symbol!r})")

        kline = pdData()
        kline.format(kLineData)
        return kline.raw()

    # 深度数据
    def depth(self, symbol: str, limit: int):
        category, newSymbol = slit(symbol, '_')
        params = {'symbol': newSymbol, 'limit': limit}
        return tryCatch(lambda: switchFn({kSpot: self._ccxt.publicGetDepth,
                                            kSwap: self._ccxt.fapiPublicGetDepth,
                                            kFuture: self._ccxt.fapiPublicGetDepth,
                                            kDelivery: self._ccxt.dapiPublicGetDepth
                                        }, key=category, params=params))

    # 成交历史
    def trades(self, symbol: str, limit: int):
        category, newSymbol = slit(symbol, '_')
        params = {'symbol': newSymbol, 'limit': limit}
        return tryCatch(lambda: switchFn({ kSpot: self._ccxt.publicGetTrades,
                                            kSwap: self._ccxt.fapiPublicGetTrades,
                                            kFuture: self._ccxt.fapiPublicGetTrades,
                                            kDelivery: self._ccxt.dapiPublicGetTrades
                                        }, key=category, params=params))

    # ── 最新价格 ──
    def tickers(self, symbol: str):
        category, newSymbol = slit(symbol, '_')
        params = {'symbol': newSymbol}
        return tryCatch(lambda: switchFn({kSpot: self._ccxt.publicGetTickerPrice,
                                        kSwap: self._ccxt.fapiPublicGetTickerPrice,
                                        kFuture: self._ccxt.fapiPublicGetTickerPrice,
                                        kDelivery: self._ccxt.dapiPublicGetTickerPrice
                                    }, key=category, params=params))

    # ── 订单本 ──
    def orderBook(self, symbol: str, limit: int = 5):
        _, symbolInfo = self.coinInfo(symbol)
        return self._ccxt.fetch_order_book(symbol=symbolInfo.get('id'), limit=limit)

    # ── 资金费率 ──
    def fundingRate(self, symbol: str, category: str):
        _, newSymbol = slit(symbol, '_')
        params = {'symbol': newSymbol}
        isUm = category in (kSwap, kFuture)
        api = self._ccxt.fapiPublicGetFundingRate if isUm else self._ccxt.dapiPublicGetFundingRate
        return tryCatch(lambda: api(params=params))
    
    # ws监听
    def _wsListen(self) -> list[tuple]:
        return [(self._ccxtSpot, 'SPOT'),
                (self._ccxtUm,   'UM_FUTURE')]
