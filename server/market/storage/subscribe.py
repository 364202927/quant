import asyncio
from typing import Any, Coroutine

import pandas as pd

from server.market import eMarketId
from server.market.baseExchange import baseExchange
from server.utils import (diff_Pdtime, evtConnect, evtFire, evtFireAsync,
                          kEvt_GetTime, kEvt_Market, kEvt_Time, pdData,
                          switchFn, timeFrame2Float, warn, threadCall, spawnTask)

kFileType = '.parquet'
kCheckOrderTime = '10s'
kKlineTimeframe = '5m'
kSaveTimeframe = '1h'


class storageSubscribe:
    """K线订阅、内存缓存和定时持久化。"""

    def __init__(self) -> None:
        self._buffer: dict[str, dict[str, dict[str, Any]]] = {}
        self._markets: dict[str, baseExchange] = {}
        self._exchanges: dict[str, baseExchange] = {}
        self._latest: dict[tuple[str, str], pd.DataFrame] = {}
        self._watchSymbols: dict[tuple[str, str], set[str]] = {}
        self._watchTasks: dict[tuple[str, str], asyncio.Task] = {}
        self._refreshTasks: dict[tuple[str, str], asyncio.Task] = {}
        self._saveTask: asyncio.Task | None = None
        evtConnect(kEvt_Market, self)
        evtConnect(kEvt_GetTime, self)
        evtFire(kEvt_Time, 'subscribe', [kCheckOrderTime, kKlineTimeframe, kSaveTimeframe])

    def setMarket(self, markets: dict[str, baseExchange]) -> None:
        self._markets = markets
        self._exchanges = {}
        for exName, exchange in markets.items():
            self._exchanges[exName] = exchange
            self._exchanges[exchange.get('id')] = exchange

    def evtProcess(self, key: object, *args: Any) -> Any:
        if key == kEvt_GetTime:
            keyTime = args[0]
            if keyTime == kCheckOrderTime:
                evtFireAsync(kEvt_Market, eMarketId['checkOrders'])
            elif keyTime == kKlineTimeframe:
                self._startTask(self._updateAll(), '5分钟K线更新')
            elif keyTime == kSaveTimeframe:
                self._scheduleSave()
            return None

        if key != kEvt_Market:
            return None
        eventId = args[0]

        def _addKlines() -> None:
            self._subscribe(args[1])

        async def _getCandles() -> pdData:
            return await self._waitCandles(args[1], args[2])

        return switchFn({eMarketId['scKline']: _addKlines,
                         eMarketId['gcKline']: _getCandles},
                        key=eventId)

    def _startTask(self, coroutine: Coroutine[Any, Any, Any], label: str) -> asyncio.Task:
        return spawnTask(coroutine, name=f"subscribe:{label}")

    def _canonicalExchange(self, exName: str) -> tuple[str, baseExchange]:
        exchange = self._exchanges.get(exName)
        if exchange is None:
            raise ValueError(f"K线订阅交易所不存在: {exName}")
        return exchange.get('id'), exchange

    def _subscribe(self, subscribeData: dict[str, list[str]]) -> None:
        subscriptions: list[tuple[str, baseExchange, str, str]] = []
        for exName, symbols in subscribeData.items():
            canonical, exchange = self._canonicalExchange(exName)
            for symbol in dict.fromkeys(symbols):
                category, symbolInfo = exchange.coinInfo(symbol)
                if symbolInfo is None:
                    raise ValueError(f"K线订阅交易对不存在: {canonical}/{symbol}")
                subscriptions.append((canonical, exchange, category, symbol))

        changedGroups: set[tuple[str, str]] = set()
        for canonical, exchange, category, symbol in subscriptions:
            slot = self._buffer.setdefault(canonical, {}).setdefault(
                symbol, {'kLine': None, 'ready': asyncio.Event()})
            group = (canonical, category)
            symbols = self._watchSymbols.setdefault(group, set())
            if symbol not in symbols:
                symbols.add(symbol)
                changedGroups.add(group)
            if not slot['ready'].is_set():
                self._scheduleRefresh(canonical, exchange, symbol, initial=True)

        for group in changedGroups:
            self._restartWatcher(group)

    def _restartWatcher(self, group: tuple[str, str]) -> None:
        current = self._watchTasks.get(group)
        if current is not None and not current.done():
            current.cancel()
        canonical, category = group
        exchange = self._exchanges[canonical]
        symbols = sorted(self._watchSymbols[group])
        self._watchTasks[group] = self._startTask(
            self._watchLoop(canonical, exchange, category, symbols),
            f"K线WS监听 {canonical}/{category}")

    async def _watchLoop(self, canonical: str, exchange: baseExchange,
                         category: str, symbols: list[str]) -> None:
        delay = 5.0
        while True:
            try:
                updates = await exchange.watchKlines(category, symbols, kKlineTimeframe)
                delay = 5.0
                for symbol, candle in updates.items():
                    formatted = pdData()
                    formatted.format([candle], style='candle')
                    self._latest[(canonical, symbol)] = formatted.raw()
                if not updates:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                raise
            except Exception as exception:
                warn(f"[subscribe] K线WS异常 {canonical}/{category}: {exception}, "
                     f"{delay:.0f}s后重试")
                await asyncio.sleep(delay)
                delay = min(delay * 1.5, 60.0)

    def _scheduleRefresh(self, canonical: str, exchange: baseExchange,
                         symbol: str, initial: bool) -> None:
        key = (canonical, symbol)
        current = self._refreshTasks.get(key)
        if current is not None and not current.done():
            return
        operation = self._initialize(canonical, exchange, symbol) if initial \
            else self._fallback(canonical, exchange, symbol)
        task = self._startTask(operation, f"K线REST更新 {canonical}/{symbol}")
        self._refreshTasks[key] = task

        def _clear(doneTask: asyncio.Task) -> None:
            if self._refreshTasks.get(key) is doneTask:
                self._refreshTasks.pop(key, None)

        task.add_done_callback(_clear)

    async def _initialize(self, canonical: str, exchange: baseExchange,
                          symbol: str) -> None:
        slot = self._buffer[canonical][symbol]
        cache: pdData | None = slot.get('kLine')
        fileName = canonical + '_' + symbol
        if cache is None:
            cache = await asyncio.to_thread(pdData, read=fileName)
            if not cache.empty():
                slot['kLine'] = cache

        if cache is None or cache.empty():
            frame = await threadCall(exchange, exchange.getKline, symbol, [], kKlineTimeframe, 0)
            if frame is None or frame.empty:
                raise RuntimeError('交易所未返回首次K线')
            cache = pdData(data=frame, style='copy')
            slot['kLine'] = cache
        else:
            lastTime = cache.raw(-1, 'candle_begin_time')
            if diff_Pdtime(lastTime) >= timeFrame2Float(kKlineTimeframe):
                frame = await threadCall(
                    exchange, exchange.getKline, symbol, [lastTime, 'now'], kKlineTimeframe, 0)
                if frame is None or frame.empty:
                    raise RuntimeError('交易所未返回增量K线')
                cache.pfConcat(frame)
        slot['ready'].set()

    async def _fallback(self, canonical: str, exchange: baseExchange,
                        symbol: str) -> None:
        frame = await threadCall(exchange, exchange.getKline, symbol, [], kKlineTimeframe, 1)
        if frame is None or frame.empty:
            raise RuntimeError('交易所未返回最新K线')
        cache: pdData = self._buffer[canonical][symbol]['kLine']
        cache.pfConcat(frame)

    async def _updateAll(self) -> None:
        for canonical, symbols in list(self._buffer.items()):
            exchange = self._exchanges.get(canonical)
            if exchange is None:
                continue
            for symbol, slot in list(symbols.items()):
                key = (canonical, symbol)
                if not slot['ready'].is_set():
                    self._scheduleRefresh(canonical, exchange, symbol, initial=True)
                    continue
                latest = self._latest.pop(key, None)
                if latest is not None and slot['kLine'] is not None:
                    slot['kLine'].pfConcat(latest)
                    continue
                self._scheduleRefresh(canonical, exchange, symbol, initial=False)

    async def _waitCandles(self, exName: str, symbol: str) -> pdData:
        canonical, _ = self._canonicalExchange(exName)
        slot = self._buffer.get(canonical, {}).get(symbol)
        if slot is None:
            raise ValueError(f"K线尚未订阅: {canonical}/{symbol}")
        await slot['ready'].wait()
        return pdData(data=slot['kLine'].raw(), style='copy')

    def _scheduleSave(self) -> None:
        if self._saveTask is not None and not self._saveTask.done():
            return
        snapshots: list[tuple[pdData, str]] = []
        for canonical, symbols in self._buffer.items():
            for symbol, slot in symbols.items():
                if not slot['ready'].is_set() or slot['kLine'] is None:
                    continue
                snapshot = pdData(data=slot['kLine'].raw(), style='copy')
                snapshots.append((snapshot, canonical + '_' + symbol + kFileType))
        self._saveTask = self._startTask(self._saveAll(snapshots), 'K线小时保存')

    async def _saveAll(self, snapshots: list[tuple[pdData, str]]) -> None:
        await asyncio.gather(*(
            asyncio.to_thread(snapshot.save2File, fileName)
            for snapshot, fileName in snapshots))

    async def shutdown(self) -> None:
        tasks = [*self._watchTasks.values(), *self._refreshTasks.values()]
        if self._saveTask is not None:
            tasks.append(self._saveTask)
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        exchanges = list({id(ex): ex for ex in self._exchanges.values()}.values())
        await asyncio.gather(*(exchange.closeKlineWs() for exchange in exchanges),
                             return_exceptions=True)
