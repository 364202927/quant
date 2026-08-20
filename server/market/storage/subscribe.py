import asyncio
from server.utils import evtConnect, kEvt_Market,kEvt_GetTime, pdData,switchFn,diff_Pdtime,timeFrame2Float,kEvt_Time,evtFire,warn,log
from server.market import eMarketId,baseExchange

kFileType = '.parquet'

# todo:这里要改
class storageSubscribe:
    "k线/成交历史/深度数据,监听更新"

    def __init__(self):
        self._buffer = {}   # 币安/ok/... = {btc:{kLine:a, depth:b, trades:c}}
        # self._depthLatest: dict[tuple, dict] = {}   # (exName,symbol) -> latest ob
        # self._tradesBuffer: dict[tuple, list] = {}  # (exName,symbol) -> [trade,...]

        self._markets = {}
        self._exMarkets = []    #全交易所
        self._exchanges = {}    #对应交易所,用于获取数据()
        evtConnect(kEvt_Market, self)
        evtConnect(kEvt_GetTime, self)
        evtFire(kEvt_Time, 'subscribe', ['5m'])

    #全交易所初始化
    def setMarket(self, markets):
        self._markets = markets
        self._exMarkets = markets
        self._exchanges = {}
        for ex in self._exMarkets.items():
            exName = ex[1].get('id')
            self._exchanges[exName] = ex[1]

    def evtProcess(self, key, *args):
        # 5m定时: 异步预拉全部订阅K线到缓存,不阻塞事件循环
        if key == kEvt_GetTime:
            if 'subscribe' in (args[1] or []):
                asyncio.create_task(self._refreshAll())
            return
        #
        if key != kEvt_Market: return
        id = args[0]
        def _addscKlne(): #更新订阅数据
            subscribeData = args[1]
            for data in subscribeData.items():
                exKey = data[0]
                if not self._buffer.get(exKey):self._buffer[exKey] = {}
                for symbol in data[1]:
                    if not self._buffer[exKey].get(symbol):
                        self._buffer[exKey][symbol] = {'kLine':None,'depth':None,'trades':None}

        # 只读缓存,绝不发REST: 策略回调在事件循环内同步执行,拉K线会卡死整个loop
        def _getCandles():
            exName, symbol = args[1], args[2]
            cached = self._buffer.get(exName, {}).get(symbol, {}).get('kLine')
            if cached is None:
                warn(f"[subscribe] K线尚未就绪,等待下次预拉: {exName}/{symbol}")
                return None
            # 返回副本: resample()会原地修改_pf,直接给出缓存对象会被策略污染并被下次预拉写进文件
            return pdData(data=cached.raw(), style='copy')

        return switchFn({eMarketId['scKline']: _addscKlne,
                        eMarketId['gcKline']: _getCandles,},
                        key=id)

    # 冷启动预拉: 策略init()注册symbol后调用一次,避免首个周期无数据
    async def warmup(self) -> None:
        await self._refreshAll()

    async def _refreshAll(self) -> None:
        for exName, symbols in list(self._buffer.items()):
            ex = self._exchanges.get(exName)
            if not ex:
                continue
            for symbol in list(symbols):
                try:
                    await self._newestCandles(ex, symbol)
                except Exception as e:
                    warn(f"[subscribe] K线更新失败 {exName}/{symbol}: {e}")

    #更新最新的k线到缓存并落盘
    async def _newestCandles(self, ex:baseExchange, symbol: str, timeFrame: str = '5m'):
        slot = self._buffer.setdefault(ex.get('id'), {}).setdefault(
            symbol, {'kLine':None,'depth':None,'trades':None})
        fileName = ex.get('id')+'_'+ symbol
        pd = slot.get('kLine')
        if not pd: #初始化
            pd = await asyncio.to_thread(pdData, read = fileName)
            if pd.empty(): #若没有保存的数据,则直接获取最新
                pd.pfConcat(await ex.getKlineAsync(symbol, [], timeFrame),False)
                slot['kLine'] = pd
                await asyncio.to_thread(pd.save2File, fileName + kFileType)
                return pd
        # 判断数据是否最新
        lastTime = pd.raw(-1, 'candle_begin_time')
        if diff_Pdtime(lastTime) < timeFrame2Float(timeFrame):
            slot['kLine'] = pd
            return pd
        #合拼最新数据
        fillPd = await ex.getKlineAsync(symbol, [lastTime,'now'], timeFrame)
        if fillPd is not None and not fillPd.empty:
            pd.pfConcat(fillPd)
        slot['kLine'] = pd
        await asyncio.to_thread(pd.save2File, fileName + kFileType)
        return pd
