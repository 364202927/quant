import asyncio,ccxt,traceback
import pandas as pd
import ccxt.pro as ccxtpro
from concurrent.futures import ThreadPoolExecutor
from server.market import (kSpot, kSwap, kFuture, kDelivery, kBuy, kSell,
                           kShort, kLong, kMarket, kLimit, eMarketId, kCancel,
                           kOrderFailedStatuses)
from server.utils import switch, switchFn, tryCatch, slit, str2ms, pdData, err, log, timeFrame2Float, evtFireAsync, kEvt_Market, threadCall, spawnTask
kSymbol = 'coinInfo'
kWsConnectTimeout = 30  # 单个ws连接建立超时(秒)

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
        self._klineWs: dict[str, ccxtpro.Exchange] = {}
        self.wsReady = asyncio.Event()   # REST预热完成+WS订阅任务已创建(不等待首条推送,避免无限等待)
        # 单worker: ccxt同步实例内部的requests.Session和nonce计数器非线程安全,
        # 多线程并发调用会偶发签名错误/连接池竞态。单worker天然串行,顺带限制单交易所REST并发
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f'ccxt-{self.__class__.__name__}')

    # 停机时由launcher调用(不能放run()的finally: 排空在途订单要早于关闭executor)
    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)

    async def closeKlineWs(self) -> None:
        clients = list({id(client): client for client in self._klineWs.values()}.values())
        self._klineWs.clear()
        if clients:
            await asyncio.gather(*(client.close() for client in clients), return_exceptions=True)

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

    def showApi(self):
        log("ccxt版本：", ccxt.__version__, "public/private + get/post + path, 驼峰编码")
        log("~~~~ccxt私有~~~~~\n", dir(self._ccxt))
        log('\n~~~~支持信息~~~~~~\n', self._ccxt.has)

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

    def requestBalanceRefresh(self) -> None:
        if self._balanceRefreshPending:
            return
        self._balanceRefreshPending = True
        spawnTask(self._refreshBalanceLater(), name=f"balanceRefresh:{self.get('title')}")

    # 取数在executor内跑,发事件回到事件循环线程: evtFireAsync要求在loop内调用
    async def _refreshBalanceLater(self) -> None:
        try:
            await asyncio.sleep(self._balanceRefreshDelay)
            bal = await threadCall(self, self.balance)
            if bal:
                evtFireAsync(kEvt_Market, eMarketId['balance'], self.get('id'), self.get('title'), bal)
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
        def _direct() -> dict | None:
            categoryData = market.get(category, {})
            direct = categoryData.get(newSymbol)
            if direct is not None:
                return direct
            return next((item for item in categoryData.values()
                         if item.get('id') == newSymbol), None)
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
                        'default': _direct
                        }, key=category)
        return category, info

    #symbol: 交易对,seTime: [开始时间, 结束时间],timeframe: K线周期,limit: 单次获取数量，0表示使用交易所最大值
    def getKline(self, symbol: str, seTime: list, timeframe: str = '5m',
                 limit: int = 0) -> pd.DataFrame | None:
        def _utcMs(value: object) -> int:
            # pdData.raw() 产生的Timestamp已是UTC0；字符串/now按公共时间入口转epoch。
            if isinstance(value, pd.Timestamp):
                timestamp = value
                if timestamp.tzinfo is not None:
                    timestamp = timestamp.tz_convert('UTC').tz_localize(None)
                return int(timestamp.value // 1_000_000)
            return str2ms(value)

        def _sortAndClip(frame: pd.DataFrame) -> pd.DataFrame:
            frame = frame.sort_values('candle_begin_time').reset_index(drop=True)
            if beginMs is not None:
                frame = frame[frame.candle_begin_time >= pd.to_datetime(beginMs, unit='ms')]
            if endMs is not None:
                frame = frame[frame.candle_begin_time <= pd.to_datetime(endMs, unit='ms')]
            return frame.reset_index(drop=True)

        beginMs = _utcMs(seTime[0]) if len(seTime) > 0 else None
        endMs = _utcMs(seTime[1]) if len(seTime) > 1 else None
        dateFrame = self._marketKline(symbol, beginMs, endMs, timeframe, limit)
        if dateFrame is None or dateFrame.empty:
            return dateFrame
        dateFrame = dateFrame.sort_values('candle_begin_time').reset_index(drop=True)
        if not endMs:
            return dateFrame
        # 准备进行分页获取
        allData = [dateFrame]
        intervalMs = int(timeFrame2Float(timeframe) * 1000)
        log(f"开始从交易所分页获取K线: {symbol}")
        pageBeginMs = beginMs
        while True:
            lastPdTime = dateFrame.iloc[-1].candle_begin_time
            lastTimeMs = int(pd.Timestamp(lastPdTime).value // 1_000_000)
            nextBeginMs = lastTimeMs + intervalMs
            if nextBeginMs > endMs:
                log("循环退出:",nextBeginMs,'>',endMs)
                break
            if pageBeginMs is not None and nextBeginMs <= pageBeginMs:
                log("分页退出: 游标未前进", nextBeginMs, '<=', pageBeginMs)
                break
            dateFrame = self._marketKline(symbol, nextBeginMs, endMs, timeframe, limit)
            # 如交易所因任何原因没有返回新数据，立刻跳出防止死循环
            if dateFrame is None or dateFrame.empty:
                break
            dateFrame = dateFrame.sort_values('candle_begin_time').reset_index(drop=True)
            allData.append(dateFrame)
            pageBeginMs = nextBeginMs
        #合并
        if len(allData) == 1:
            return _sortAndClip(allData[0])
        allpd = pdData()
        allpd.format(allData, style='concat')
        return _sortAndClip(allpd.raw())

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
        return await threadCall(self, fn, **kwargs)

    def _klineWsClient(self, category: str) -> ccxtpro.Exchange:
        client = self._klineWs.get(category)
        if client is not None:
            return client
        exchangeClass = getattr(ccxtpro, self.__class__.__name__)
        defaultType = 'spot' if category == kSpot else 'swap'
        client = exchangeClass({
            'enableRateLimit': True,
            'options': {'defaultType': defaultType},
        })
        self._klineWs[category] = client
        return client

    async def watchKlines(self, category: str, symbols: list[str],
                          timeframe: str = '5m') -> dict[str, list]:
        symbolMap: dict[str, str] = {}
        subscriptions: list[list[str]] = []
        for symbol in symbols:
            symbolCategory, symbolInfo = self.coinInfo(symbol)
            if symbolCategory != category or symbolInfo is None:
                raise ValueError(f"K线订阅交易对不存在: {self.get('id')}/{symbol}")
            unified = symbolInfo['symbol']
            symbolMap[unified] = symbol
            subscriptions.append([unified, timeframe])
        if not subscriptions:
            return {}
        result = await self._klineWsClient(category).watch_ohlcv_for_symbols(
            subscriptions, limit=1)
        latest: dict[str, list] = {}
        for unified, timeframes in result.items():
            candles = timeframes.get(timeframe, []) if isinstance(timeframes, dict) else []
            if candles and unified in symbolMap:
                latest[symbolMap[unified]] = candles[-1]
        return latest

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
    # 修改订单
    def editOrder(self, orderID: str, symbol: str, side: str,amount: float, price: float) -> dict | None:
        category, symbolInfo = self.coinInfo(symbol)
        if not symbolInfo or not orderID:
            return None
        params = self._orderParams(category)
        return self._ccxt.edit_order(str(orderID), symbolInfo.get('symbol') or symbolInfo.get('id'),'limit', side, amount, price, params)
    #交易所/账户类型相关的 fetch/edit 参数
    def _orderParams(self, category: str) -> dict:
        return {}
    
    # WebSocket 入口
    async def run(self) -> None:
        ws_pairs = self._wsListen()
        if not ws_pairs:
            self.wsReady.set()
            return

        async def _tryConnect(exchange, market_type):
            try:
                await asyncio.wait_for(exchange.fetch_balance(), timeout=kWsConnectTimeout)
                return (exchange, market_type)
            except asyncio.TimeoutError:
                log(f"[{self.get('title')}] {market_type} WS连接超时({kWsConnectTimeout}s),跳过该连接")
            except Exception as e:
                log(f"[{self.get('title')}] {market_type} WS连接失败: {e},跳过该连接")
            return None

        results = await asyncio.gather(*[_tryConnect(e, mt) for e, mt in ws_pairs])
        connected = [pair for pair in results if pair is not None]
        if not connected:
            err(f"[{self.get('title')}] 全部WS连接失败,本次运行该交易所没有任何实时推送")

        tasks = [
            spawnTask(coro, name=f"ws:{label}:{market_type}:{self.get('title')}")
            for exchange, market_type in connected
            for label, coro in (('balance', self._listen_balance(exchange, market_type)),
                                ('orders', self._listen_orders(exchange, market_type)))]
        self.wsReady.set()
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
                status = str(order.get('status') or '').lower()
                if status != 'closed' and status not in kOrderFailedStatuses:
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