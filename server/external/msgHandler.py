import asyncio
import os
import random
import pandas as pd
from server.core.engine import engine
from server.utils import switchFn,evtConnect, rtWeb,evtFire,kEvt_Web,kEvt_Engine,log,pdData
from server.utils.fileConfig import g_config

eMsgId = {
    #set数据,内部通知
    'sPage':10,

    #get数据，获取信息
    'eWebInit':1000, #web初始化
    'ePage_k':1001,  #行情page 
    'ePage_cta':1002, #策略管理page
    'ePage_test':1003, #回测page
    'ePage_order':1004, #订单管理
    #save数据，设置信息
    'eSaveFile':10000, #保存
    'eStartBackTest':11000,#开启回测
}

class msgHandler:
    "消息事件处理器"

    BACKTEST_TIMEOUT = 600  # 隔离回测最长等待秒数, 仅防策略回调异常导致的永久挂起
    SAMPLE_BARS = 365 * 24 * 12  # 模拟回测随机截取约 1 年的 5m K线

    def __init__(self):
        self.__page = 0
        evtConnect(kEvt_Web, self)
    
    def idTransform(self, id, msg):
        def initWeb():
            info = g_config.info()
            external = g_config.external() 
            user = {
                "userName": info.get("userName", ""),
                "ccxtRetry": info.get("ccxtRetry", 3),
                "console_e": bool(external.get("console", {}).get("enable", 0)),
                "tg_e": bool(external.get("tg", {}).get("enable", 0)),
                "feishu_e": bool(external.get("feishu", {}).get("enable", 0)),
                'page': self.__page
            }
            apiKey = {
                "market": g_config.marketsApi(),
                "newsletter": g_config.newsletterApi(),
                "ai": g_config.aiApi()
            }
            # print("~~~~~~~initWeb~~~~~~~~",user,apiKey)
            # 返回数据: user配置 + apiKey配置+start文件
            return {"user": user, "apiKey": apiKey} #todo:还有start文件
        async def initMarketTrends():
            args = msg[0] if msg else []
            coin = args[0].strip() if args else ''
            start = str(args[1]).strip() if len(args) > 1 and args[1] else ''
            end = str(args[2]).strip() if len(args) > 2 and args[2] else ''
            if not coin:
                return await asyncio.to_thread(self._marketCoins)
            return await asyncio.to_thread(self._marketKline, coin, start, end)
        def initStartFile():
            return
        def initBacktesting():
            return self.callTask('main','getActiveTasks')
        def initOrders():
            return
        def saveConfig():#保存设置
            g_config.setConfig(msg[0])
            g_config.saveFile()
            #todo:是否重启服务器
            return
        async def startBackTest():#开启回测: id 0=数据隔离, 1=快速回测, 其他=模拟回测取数(symbol)
            args = msg[0][0] if msg and msg[0] else {}
            return await self._runBackTest(args.get('id'), args.get('selectedTask'))
        return switchFn({eMsgId['eWebInit']: initWeb,
                        eMsgId['ePage_k']: initMarketTrends,
                        eMsgId['ePage_cta']:initStartFile,
                        eMsgId['ePage_test']:initBacktesting,
                        eMsgId['ePage_order']:initOrders,
                        eMsgId['eSaveFile']:saveConfig,
                        eMsgId['eStartBackTest']:startBackTest},
                        key=id)
    
    async def _runBackTest(self, id, taskName: str | None = None) -> dict:
        try:
            if id == 1:  # 快速回测: 全量一次算完
                return self.callTask(taskName, 'startStrategy')
            if id == 0:  # 数据隔离: 定时器逐段揭示K线
                evtFire(kEvt_Engine, taskName, 'beginTest')
                await self._waitBackTest(taskName)
                return self.callTask(taskName, 'getBacktestResult')
            return await asyncio.to_thread(self._sampleKline, str(id))  # 模拟回测: id 即 symbol
        except Exception as e:
            log(f"[msgHandler] 回测启动失败: {e}")
            return {"error": str(e)}

    # 模拟回测取数: 随机截取约 1 年 5m K线, 由前端按所选周期聚合回放
    def _sampleKline(self, symbol: str) -> dict:
        if not symbol or os.path.basename(symbol) != symbol or symbol not in self._marketCoins():
            return {"error": f"未知symbol: {symbol}"}
        data = pdData()
        if not data.readFile(symbol, isFull=True):
            return {"error": f"未找到K线数据: {symbol}"}
        frame = data.raw()
        if len(frame) > self.SAMPLE_BARS:
            start = random.randint(0, len(frame) - self.SAMPLE_BARS)
            frame = frame.iloc[start:start + self.SAMPLE_BARS]
        columns = ['candle_begin_time', 'open', 'high', 'low', 'close', 'vol']
        if 'funding_bps' in frame.columns:
            columns.append('funding_bps')
        frame = frame[columns]
        return {"kLine": rtWeb({'kLine': frame})['kLine']}

    # 隔离回放由定时器推进, 轮询到结束后再取结果; 上限避免策略回调异常导致请求永久挂起
    async def _waitBackTest(self, taskName: str) -> None:
        deadline = asyncio.get_running_loop().time() + self.BACKTEST_TIMEOUT
        while True:
            state = evtFire(kEvt_Engine, taskName, 'testState')
            if not state:
                raise RuntimeError(f"任务 {taskName} 不支持数据隔离回测")
            if not state.get('testing'):
                return
            if asyncio.get_running_loop().time() > deadline:
                raise TimeoutError(f"回测超时(>{self.BACKTEST_TIMEOUT}s)")
            await asyncio.sleep(0.1)

    # 调用engine功能
    def callTask(self, taskName, fnName):
        rt = evtFire(kEvt_Engine, taskName, fnName)
        if taskName =='main':
            return rt
        return rtWeb(rt)
    
    # 历史行情文件中的全部币种名
    def _marketCoins(self) -> list[str]:
        root = g_config.fils('marketsPath')
        if not os.path.isdir(root):
            return []
        names = set()
        for year in os.listdir(root):
            yearPath = os.path.join(root, year)
            if not (year.isdigit() and len(year) == 4 and os.path.isdir(yearPath)):
                continue
            for fileName in os.listdir(yearPath):
                if fileName.endswith('.parquet'):
                    names.add(os.path.splitext(fileName)[0])
        return sorted(names)

    # 指定币种的全部历史K线,可传start/end(UTC,闭区间)做时间剪裁
    def _marketKline(self, coin: str, start: str = '', end: str = '') -> list[dict]:
        if os.path.basename(coin) != coin or coin not in self._marketCoins():
            return []
        data = pdData()
        try:
            loaded = data.readFile(coin, isFull=True)
        except Exception as exception:
            log(f"[msgHandler] 行情读取失败 {coin}: {exception}")
            return []
        if not loaded:
            return []
        startTime = pdData._normalizeTime(pd.to_datetime(start, errors='coerce')) if start else None
        endTime = pdData._normalizeTime(pd.to_datetime(end, errors='coerce')) if end else None
        if (start and pd.isna(startTime)) or (end and pd.isna(endTime)):
            return []
        frame = data.raw()
        if startTime is not None:
            frame = frame[frame['candle_begin_time'] >= startTime]
        if endTime is not None:
            frame = frame[frame['candle_begin_time'] <= endTime]
        if frame.empty:
            return []
        return rtWeb({'kLine': frame})['kLine']

    # 处理web id
    def process(self, id, msg):
        print(f"~~~~~~~~~~[消息处理]~~~~~~~~ 消息ID: {id}, 参数: {msg}")
        rt = self.idTransform(id,msg)
        return rt

    #evt消息
    def evtProcess(self, key, *args):
        id = args[0]
        msg = list(args[1:]) if len(args) > 1 else []
        def setPage():
            self.__page = msg[0] if msg else 0
        if id == eMsgId['sPage']:
            setPage()
            return None
        return self.idTransform(id, msg)