import asyncio,ccxt,traceback
import pandas as pd
import ccxt.pro as ccxtpro
from server.market import kSpot, kSwap, kFuture, kDelivery, kBuy, kSell, kShort, kLong, kMarket, kLimit, eMarketId,kCancel
from server.utils import switch, switchFn, tryCatch, slit, str2ms, pdData, err, log, utc_now, timeFrame2Float, evtFireAsync, kEvt_Market
kSymbol = 'coinInfo'

def _backoff(start: float = 5.0, factor: float = 1.5, cap: float = 60.0):
    delay = start
    while True:
        yield delay
        delay = min(delay * factor, cap)

class baseExchange:

    def __init__(self, description: str, maxLimit: int):
        self.__description = description
        self._maxLimit = maxLimit
        self._ccxt = None
        self._title = ''        #绑定的交易所名字
        self._acc = {}          #账号
        self._info = { kSymbol: {}, 'api': {}} #coin币种信息,api交易所api信息
        self._balanceRefreshPending = False
        self._balanceRefreshDelay = 1.0

    def get(self, key: str):
        return switch({
            'id': self.__class__.__name__,
            'des': self.__description,
            'title':self._title,
            'ccxt': self._ccxt,
            'coinInfo': self._info[kSymbol]}, key=key)

    def enroll(self, config: dict,title:str):
        self._create(config)
        self._title = title
        self._utc = utc_now()

    def showApi(self):
        print("ccxt版本：", ccxt.__version__, "public/private + get/post + path, 驼峰编码")
        print("~~~~ccxt私有~~~~~\n", dir(self._ccxt))
        print('\n~~~~支持信息~~~~~~\n', self._ccxt.has)

    #账户信息
    def balance(self,isSpot = True):
        if not isSpot: return
        bal = self._ccxt.fetch_balance()
        def _pos(src: dict) -> dict:
            return {k: fv for k, v in src.items() if v and (fv := float(v)) > 0}
        self._acc = {
            'total': _pos(bal.get('total', {})),
            'free':  _pos(bal.get('free', {})),
        }
        return self._acc

    def refreshBalance(self) -> dict:
        bal = self.balance()
        if bal:
            evtFireAsync(kEvt_Market, eMarketId['balance'], self.get('id'), self.get('title'), bal)
        return bal

    def requestBalanceRefresh(self) -> None:
        if self._balanceRefreshPending:
            return
        self._balanceRefreshPending = True
        asyncio.create_task(self._refreshBalanceLater())

    async def _refreshBalanceLater(self) -> None:
        try:
            await asyncio.sleep(self._balanceRefreshDelay)
            await asyncio.to_thread(self.refreshBalance)
        except Exception as e:
            log(f"[{self.get('title')}] 余额刷新失败: {e}")
        finally:
            self._balanceRefreshPending = False

    #余额查询
    def accFree(self, coin: str = '', isPm: bool = False):
        return self._acc.get('free', {}).get(coin or 'USDT', 0)

    #当前交易所的所有币种
    def initMarkets(self, reset: bool = False) -> dict:
        if not reset and self._info.get(kSymbol):
            return self._info[kSymbol]
        self._info[kSymbol] = {kSpot: {}, kSwap: {}, kFuture: {}, kDelivery: {}}
        markets = self._ccxt.loadMarkets()
        for symbol, market in markets.items():
            if market['active'] and market['type'] in self._info[kSymbol]:
                self._info[kSymbol][market['type']][symbol] = {
                    'id': market['id'],
                    'symbol':symbol,
                    'step':market['precision']['amount'],
                    'priceStep': market['precision'].get('price'),
                    'market': market['limits']['market'],
                    'amount': market['limits']['amount'],   #币个数
                    'price': market['limits']['price'],
                    'cost': market['limits']['cost']}
        return self._info[kSymbol]

    def coinInfo(self, symbol: str) -> tuple:
        category, newSymbol = slit(symbol, '_')
        def _find():
            res = slit(newSymbol, '-')
            futureSymbol = newSymbol if res == False else res[0]
            catData = market.get(category, {})
            direct = catData.get(futureSymbol)
            if direct is not None:
                return direct
            keys = sorted([k for k in catData if k.split(':')[0] == futureSymbol],
                           key=lambda k: k.split('-')[-1])
            if not keys:
                return None
            sel = int(res[1]) if res else 0
            return catData.get(keys[sel])
        market = self.get("coinInfo")
        info = switchFn({kDelivery: _find,
                        kFuture: _find,
                        'default': lambda: market.get(category, {}).get(newSymbol)
                        }, key=category)
        return category, info

    #symbol: 交易对,seTime: [开始时间, 结束时间],timeframe: K线周期,limit: 单次获取数量，0表示使用交易所最大值
    def getKline(self, symbol: str, seTime: list, timeframe: str = '5m', limit: int = 0):
        beginMs = str2ms(seTime[0], self._utc) if len(seTime) > 0 else None
        endMs = str2ms(seTime[1], self._utc) if len(seTime) > 1 else None
        dateFrame = self._marketKline(symbol, beginMs, endMs, timeframe, limit)
        if dateFrame is None or dateFrame.empty or not endMs:
            return dateFrame
        # 准备进行分页获取
        allData = [dateFrame]
        intervalMs = int(timeFrame2Float(timeframe) * 1000)
        log(f"开始从交易所分页获取K线: {symbol}")
        while True:
            lastPdTime = dateFrame.iloc[-1].candle_begin_time
            lastTimeMs = int((pd.Timestamp(lastPdTime) + pd.Timedelta(hours=self._utc)).timestamp() * 1000)
            nextBeginMs = lastTimeMs + intervalMs
            log("循环退出:",nextBeginMs,'>',endMs)
            if nextBeginMs > endMs:
                break
            dateFrame = self._marketKline(symbol, nextBeginMs, endMs, timeframe, limit)
            # 如交易所因任何原因没有返回新数据，立刻跳出防止死循环
            if dateFrame is None or dateFrame.empty:
                break
            allData.append(dateFrame)
        #合并
        if len(allData) == 1:
            return allData[0]
        allpd = pdData()
        allpd.format(allData, style='concat')
        return allpd.get()

    async def order(self, typeState: str, symbol: str, totelPrice, amount: float, price: float | None = None, isMarket=False, inForce='GTC', posSide: str | None = None, lv: int = 1, clientOrderId: str | None = None):
        category, symbolInfo = self.coinInfo(symbol)
        kwargs = {'state': typeState, 'symbol': symbolInfo['id']}
        isSpot = category == kSpot
        def _sporOrder(state: str, symbol, totelPrice=None, amount=None, price=None, clientOrderId=None):
            extraParams = {'clientOrderId': clientOrderId} if clientOrderId else {}
            params = {'symbol': symbol.get('id'),
                    'side': state,
                    'type': kMarket,
                    'amount': amount,
                    'price':None}
            if amount and price:
                params.update(type=kLimit, price=price)
            elif state == kBuy and amount is None:
                extraParams['quoteOrderQty'] = totelPrice
            elif state == kSell and amount is None:
                raise ValueError(f"现货卖出缺少 amount: {symbol.get('id')}")
            if extraParams:
                params['params'] = extraParams
            return self._ccxt.create_order(**params)
        def _setkWargs():
            nonlocal kwargs
            kwargs.update(symbol=symbolInfo, totelPrice=totelPrice, amount=amount, price=price, clientOrderId=clientOrderId)
            if isSpot:
                return
            kwargs.update(symbol=symbol, lv=lv, posSide=posSide, isMarket=isMarket, inForce=inForce)
            kwargs.pop('totelPrice', None)
        def _setCancel():
            nonlocal kwargs
            kwargs = {'id':totelPrice, 'symbol':symbolInfo.get('symbol')}
            if isSpot:
                return
            kwargs['symbol'] = symbol
        def _cancelSpot(symbol: str, id: str):
            if id:
                return self._ccxt.cancelOrder(id, symbol)
            return [self._ccxt.cancelOrder(o.get('id'), symbol) for o in self._ccxt.fetch_open_orders(symbol)]
        #logic
        switchFn({kCancel: _setCancel,
                    'default': _setkWargs}, 
                    key=typeState)
        
        log("~~~~~~send order~~~~~~~", kwargs)
        dispatch = {kBuy: _sporOrder if isSpot else self._contractOrder,
                    kSell: _sporOrder if isSpot else self._contractOrder,
                    kCancel: _cancelSpot if isSpot else self._cancelOrder}
        fn = dispatch.get(typeState)
        if not fn:
            return False
        return await asyncio.to_thread(fn, **kwargs)
    #获取个人交易记录
    def trades(self, symbol: str, limit: int = 500) -> list[dict]:
        category, symbolInfo = self.coinInfo(symbol)
        if category == kSwap:
            return self._trades(symbol, limit)
        rt = tryCatch(lambda: self._ccxt.fetch_my_trades(symbolInfo['symbol'], limit=limit))
        return rt or []

    #批量下单
    def batchOrders(self, category: str, orders: list[dict]) -> list:
        if not orders or len(orders) > 5:
            err("batchOrders: 订单数量需在1-5之间")
            return []
        return self._batchOrders(category, orders)
    
    # WebSocket 入口
    async def run(self) -> None:
        ws_pairs = self._wsListen()
        if not ws_pairs:
            return
        await asyncio.gather(*[e.fetch_balance() for e, _ in ws_pairs])
        tasks = [
            asyncio.create_task(coro)
            for exchange, market_type in ws_pairs
            for coro in (self._listen_balance(exchange, market_type),
                        self._listen_orders(exchange, market_type))]
 
        log(f"~~~~ws 开始监听~~~")
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            raise
        finally:
            await self._close_ws(ws_pairs)

    def _wsListen(self) -> list[tuple[ccxtpro.Exchange, str]]:
        return []
    async def _close_ws(self, ws_pairs: list[tuple]) -> None:
        await asyncio.gather(*[e.close() for e, _ in ws_pairs],return_exceptions=True)

    async def _ws_loop(self, label: str, market_type: str, callback):
        delays = _backoff()
        while True:
            try:
                await callback()
                delays = _backoff()
            except asyncio.CancelledError:
                raise
            except ccxt.AuthenticationError as e:
                delay = next(delays)
                print(f"[{market_type}] {label}认证失败: {e} — {delay:.0f}s 后重试")
                await asyncio.sleep(delay)
            except ccxt.NetworkError as e:
                delay = next(delays)
                print(f"[{market_type}] {label}网络异常: [{type(e).__name__}] {e} — {delay:.0f}s 后重试")
                await asyncio.sleep(delay)
            except Exception as e:
                delay = next(delays)
                print(f"[{market_type}] {label}严重错误: {e}")
                traceback.print_exc()
                await asyncio.sleep(delay)

    async def _listen_balance(self, exchange, market_type: str):
        async def _on_balance():
            balances = await exchange.watch_balance()
            if market_type == 'SPOT':
                self._sync_balance(balances)
            else:
                self.requestBalanceRefresh()
            evtFireAsync(kEvt_Market, eMarketId['wsBalance'], self.get('id'), self.get('title'), balances)
        await self._ws_loop('资金流', market_type, _on_balance)

    def _sync_balance(self, balances: dict) -> None:
        if not isinstance(balances, dict):
            return
        for key in ('free', 'used', 'total'):
            data = balances.get(key, {})
            if isinstance(data, dict):
                self._acc.setdefault(key, {}).update({k: float(v) for k, v in data.items() if v is not None})

    async def _listen_orders(self, exchange: ccxtpro.Exchange, market_type: str, symbol=None) -> None:
        async def _on_orders():
            orders = await exchange.watch_orders(symbol)
            for order in orders:
                log(f"[{market_type}] ws订单更新: {order['status']} : {order}")
                if order['status'] not in ('closed', 'canceled'):
                    continue
                evtFireAsync(kEvt_Market, eMarketId['wsOrder'], self.get('title'), order)
                if market_type != 'SPOT':
                    self.requestBalanceRefresh()
        await self._ws_loop('订单流', market_type, _on_orders)

    def _create(self, config: dict):
        self._info['api'] = {'apiKey': config['apiKey'], 'secret': config['secret']}
    def orderBook(self, symbol: str, limit: int = 5): pass
    def depth(self, symbol, limit): pass
    def tickers(self, symbol): pass
    def findOrder(self, symbol: str, orderId: str = '',isPos = True,isOpen = False): pass 
    def _accPm(self, account, coin) -> float: return 0
    def _contractOrder(self, state: str, symbol: dict, amount: float, isMarket, inForce, price: float | None = None, lv: int = 1, posSide: str | None = None, clientOrderId: str | None = None): pass
    def _cancelOrder(self, symbol: str, id: str): pass
    def _batchOrders(self, category, orders): pass
    def _trades(self, symbol: str, limit: int = 500) -> list[dict]:pass
    def _marketKline(self, symbol: str, beginTime: int | None, endTime = None, timeframe: str = '5m', limit: int = 1000):
        return self._ccxt.fetch_ohlcv(symbol=symbol, timeframe=timeframe, since=beginTime, limit=limit)