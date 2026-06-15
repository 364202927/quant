# import asyncio
# import aiohttp
import json
# import datetime

from server.market.baseExchange import *
from server.market import kPm, eMarketId
# from server.utils.science import binanceTimestamp
from server.utils import timeFrame2Float, sec2min, logFormat, log, evtFireAsync, kEvt_Market, str2time,binanceTimestamp

kMaxLimit = 1000   # 现货最大 K 线
kfMaxLimit = 1500  # 合约最大

def _wsCreate(cls: type,api_key: str,secret: str,proxy: str,**options) -> ccxtpro.Exchange:
    return cls({
        'apiKey':          api_key,
        'secret':          secret,
        'socksProxy':      proxy,
        'wsSocksProxy':    proxy,
        'enableRateLimit': True,
        'timeout':         30_000,
        'options':         options,
    })
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
    
    def _create(self, config: dict):
        super()._create(config)
        api = self._info['api']
        proxy = 'socks5://127.0.0.1:10808'
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
        self._ccxtSpot = _wsCreate(ccxtpro.binance, api['apiKey'], api['secret'], proxy,defaultType='spot')
        self._ccxtUm = _wsCreate( BinancePAPI,api['apiKey'], api['secret'], proxy,defaultType='papi', portfolioMargin=True)

    # 根据币类型返回对应ccxt实例
    # def _getEx(self, typeEx: str):
    #     return switch({
    #         kSpot: self._ccxt,
    #         kSwap: self._um,
    #         # kFuture: self._um,
    #         # kDelivery: self._cm
    #     }, key=typeEx)
    #     return self._ccxt

    # def _selectApi(self, category: str, pmUm, pmCm, normalUm, normalCm):
    #     """根据 category 和 PM 模式选择对应 API (已废弃: 仅支持 PM 模式 u本位)"""
    #     isUm = category in (kSwap, kFuture)
    #     if self._isPm:
    #         return pmUm if isUm else pmCm
    #     ex = self._getEx(category)
    #     return normalUm(ex) if isUm else normalCm(ex)

    # def markets(self, reset=False):
    #     def _loadMarket(coin: dict, exchange):
    #         markets = exchange.loadMarkets()
    #         for symbol, market in markets.items():
    #             if market['active']:
    #                 contractStep = market['precision']['amount']#合约步长,最少张数
    #                 contractSize = market['contractSize']       #合约面值
    #                 coin[symbol] = {
    #                     'id': market['id'],
    #                     'market': market['limits']['market'], #市价张数
    #                     'amount': market['limits']['amount'], #合约张数
    #                     'price': market['limits']['price'],
    #                     'cost': market['limits']['cost']}
    #                 # print("~cm~~",market)
    #     #
    #     super().markets(reset)      #u本位+u交割+现货
    #     coin = self._info['coin']
    #     # print("~~~~~~markets~~~~~~~~~")
    #     # _loadMarket(coin[kDelivery], self._cm)   # 币本位+交割
    #     # logFormat(coin)
    #     # exit()
    #     return coin
    
    #http取账号数据
    def balance(self) -> dict:
        bal = super().balance() #现货数据
        pmAcc = self._ccxt.sapiGetPortfolioAccount() #统一账号总数据
        pmCoin = self._ccxt.papi_get_balance()      #统一账号里存在币种
        coin = {}
        for item in pmCoin:
            asset = item.get('asset')
            twb = float(item.get('totalWalletBalance', 0))
            # cmf = float(item.get('crossMarginFree', 0))
            # umf = float(item.get('umWalletBalance', 0))
            # cmf2 = float(item.get('cmWalletBalance', 0))
            if twb == 0:# and cmf == 0 and umf == 0 and cmf2 == 0:
                continue
            coin[asset] = twb#{'total': twb} #'free': cmf,'umFree': umf, 'cmFree': cmf2,
        pmData = {
            'equity': float(pmAcc['accountEquity']),
            'free': float(pmAcc['totalAvailableBalance']), 
            'uniMMR': float(pmAcc['uniMMR']),
            'danger': float(pmAcc['accountMaintMargin']), #强平金额
            'total': coin,
        }
        # 返回格式:{'total':{},'free':{},kPm:{}}
        self._acc[kPm] = pmData
        return self._acc

    def accFree(self, coin: str = '',isPm = False):
        if isPm:
            return self._acc[kPm].get('free') #联合账号可用金额
        return super().accFree(coin)

    # ── 合约订单查询 ──
    def findOrder(self, symbol: str, orderId: int  = -1,isOpen = False,isPos = True):
        # print("~~~~findOrder~~~~",symbol, orderId)
        id,category = '',''
        if symbol:
            category, symbolInfo = self.coinInfo(symbol)
            id = symbolInfo.get('id')
        open_orders, pos_orders = [],[]
        # 现货挂单
        if category == kSpot: #orderId >= 0: 
            # if orderId == '0':
            #     return self._ccxt.fetch_open_orders() 
            # order = tryCatch(lambda: self._ccxt.fetch_order(id=orderId, symbol=symbol))
            # return self._ccxt.fetch_order(id=orderId, symbol=symbol)
            # print("~orderId~~~",orderId,id)
            open_orders = self._ccxt.fetch_open_orders(id)
            # print(f"币种: {order['symbol']}, ID: {order['id']}, 价格: {order['price']}")
            print('~~~~~open_orders~~~~~~',open_orders)
            if orderId >= 0:
                # open_orders = [order for order in open_orders if order['symbol'] == id or order['id'] == orderId]
                open_orders = [order.get('info') for order in open_orders if order.get('info')['symbol'] == id or order.get('info')['orderId'] == orderId]
            return open_orders
        #查挂单
        if isOpen:
            open_orders = self._ccxt.papi_get_um_openorders()
            if id != '':
                open_orders = [order for order in open_orders if order['symbol'] == id]
            # [{'orderId': '94001018131', 'symbol': 'DOGEUSDT', 'status': 'NEW', 'clientOrderId': 'H5ERnMC8YrvEwuKh7mj916', 'price': '0.070000', 'avgPrice': '0.000000',
            #     'origQty': '1226', 'executedQty': '0', 'cumQuote': '0.000000', 'timeInForce': 'GTC', 'type': 'LIMIT', 'reduceOnly': False, 'side': 'BUY', 'positionSide': 'LONG',
            #     'origType': 'LIMIT', 'time': '1772197398894', 'updateTime': '1772197398894', 'goodTillDate': '0', 'selfTradePreventionMode': 'EXPIRE_MAKER', 'priceMatch': 'NONE'}]
        #查仓位
        if isPos:
            orders = self._ccxt.papiGetUmPositionRisk()
            pos_orders = []
            for order in orders:
                status = float(order['positionAmt']) > 0 and kBuy or kSell
                newData = { #查 仓位格式
                    'symbol':order['symbol'],
                    'dir':status+'_'+order['positionSide'],
                    'open': order['entryPrice'],
                    'lv':order['leverage'],
                    'unRealized':order['unRealizedProfit'],
                    'amount':abs(float(order['positionAmt'])),
                }
                pos_orders.append(newData)
            if id != '':
                pos_orders = [pos for pos in pos_orders if pos['symbol'] == id and float(pos['positionAmt']) != 0]
            # [{'symbol': 'DOGEUSDT', 'positionAmt': '-53.0', 'entryPrice': '0.09522', 'markPrice': '0.09406', 'unRealizedProfit': '0.06148', 'liquidationPrice': '32.22623582', 
            #   'leverage': '1', 'positionSide': 'SHORT', 'updateTime': '1772197402977', 'maxNotionalValue': '200000000', 'notional': '-4.98518', 'breakEvenPrice': '0.09517239'}, 
        
        return open_orders, pos_orders
    # ── 合约下单 ──
    def _contractOrder(self, state: str, symbol: dict, amount: float, isMarket: bool, inForce: str, price: float | None = None, lv: int = 1, posSide: str | None = None):
        def _pmOrder(state: str, isUm: bool, params: dict):
            #设置杠杆
            lvApi = self._ccxt.papiPostUmLeverage if isUm else self._ccxt.papiPostCmLeverage
            lvApi(params={'symbol': symbolInfo.get('id'), 'leverage': lv, 'timestamp': binanceTimestamp()})
            # orderApi = self._ccxt.papiPostUmOrder if isUm else self._ccxt.papiPostCmOrder
            return  self._ccxt.papiPostUmOrder(params=params)#orderApi(params=params)
            # return switchFn({kBuy: orderApi,
            #                 kSell: orderApi,
            #                 # 'cancel': cancelApi
            #             }, key=state, params=params)
        # def _normalOrder(state: str, category: str, params: dict):
            # ex = self._getEx(category)
            # return self._ccxt.create_order(**params)
            # return tryCatch(lambda: switchFn({kBuy: ex.create_order,
            #                                 kSell: ex.create_order,
            #                                 'cancel': ex.cancel_order
            #                                 }, key=state, **params))
        #
        category, symbolInfo = self.coinInfo(symbol)
        isUm = category in (kSwap, kFuture)
        params = {'symbol': symbolInfo.get('id')}
        # if state in (kBuy, kSell):
        params.update({
            'side': state.upper(),
            'positionSide': posSide,
            'quantity': amount,#self._ccxt.amount_to_precision(symbolInfo['symbol'],amount),
            'type': kMarket if isMarket else kLimit})
        if not isMarket:
            params['price'] = price#self._ccxt.price_to_precision(symbolInfo['symbol'], price)
            params['timeInForce'] = inForce
            # postOnly #强制订单只能作为 Maker,需要配合偏离一下现价
        # elif state == 'cancel':
            # params['orderId'] = symbol
            # params = {'orderId':price}
        #平仓时只减仓
        if (params['side'] == kBuy and params['positionSide'] == kShort) or \
            (params['side'] == kSell and params['positionSide'] == kLong):
            params['reduceOnly'] = True
        print("~~~~_contractOrder~~~~~~", isUm, lv, params)
        # if self._isPm: # PM 模式
        # return _pmOrder(state, isUm, params)
        # Normal 模式
        # return _normalOrder(state, category, params)

    # ── 合约撤单 ──
    def _cancelOrder(self, symbol: str, id: str):
        category, symbolInfo = self.coinInfo(symbol)
        params = {'symbol': symbolInfo.get('id'),
                  'orderId': id,
                  'timestamp': binanceTimestamp()}
        # 仅支持 PM 模式 u本位
        return self._ccxt.papiDeleteUmOrder(params=params)

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

    # def checkPosition(self, category: str = '', symbol: str | None = None):
    # def checkPosition(self):
    #     pass
    
    # ── K线 ──
    def _marketKline(self, symbol: str, beginTime, endTime =None, timeframe: str = '5m', limit: int = 0):
        category, newSymbol = slit(symbol, '_')
        if category == kSpot:
            self._maxLimit = kMaxLimit
            kLineData = super()._marketKline(newSymbol, beginTime, endTime, limit=limit if limit else self._maxLimit)
        elif category in (kSwap, kFuture, kDelivery):
            self._maxLimit = kfMaxLimit
            params = {'symbol': newSymbol,
                      'interval': timeframe,
                      'limit': limit if limit else kfMaxLimit}
            if beginTime is not None:
                params['startTime'] = beginTime
            if endTime is not None:
                params['endTime'] = endTime
            # api = self._um.fapiPublicGetKlines# if category != kDelivery else self._ccxt.dapiPublicGetKlines
            kLineData = self._ccxt.fapiPublicGetKlines(params=params) #tryCatch(lambda: api(params=params))
            if not kLineData:
                return None
        pd = pdData()
        pd.format(kLineData, utc=self._utc)
        return pd.get()

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
    def orderBook(self, symbol: str, limit: int):
        category, symbolInfo = self.coinInfo(symbol)
        return self._ccxt.fetch_order_book(symbol=symbolInfo.get('id'), limit=limit)

    # ── 资金费率 ──
    def fundingRate(self, symbol: str, category: str):
        _, newSymbol = slit(symbol, '_')
        params = {'symbol': newSymbol}
        isUm = category in (kSwap, kFuture)
        api = self._ccxt.fapiPublicGetFundingRate if isUm else self._ccxt.dapiPublicGetFundingRate
        return tryCatch(lambda: api(params=params))
    
    # async def _close_ws(self):
    #     """关闭 ccxtpro WebSocket 连接"""
    #     for attr in ('_ccxtSpot', '_ccxtUm'):
    #         ex = getattr(self, attr, None)
    #         if ex:
    #             try:
    #                 await ex.close()
    #             except Exception:
    #                 pass

    # ws监听
    def _wsListen(self) -> list[tuple]:
        return [(self._ccxtSpot, 'SPOT'),
                (self._ccxtUm,   'UM_FUTURE')]