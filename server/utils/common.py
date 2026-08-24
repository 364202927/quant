import pickle, json, os, requests, inspect, asyncio, gzip, webbrowser, sys, math, traceback
from importlib import import_module
from functools import partial
from pydispatch import dispatcher
from server.utils import eTimeTs, kEvt_Web
from datetime import datetime, date, timedelta
from pathlib import Path
import pandas as pd
from typing import Any
import numpy as np

def publicIp():
    response = requests.get('https://api.ipify.org?format=json')
    public_ip = response.json()['ip']
    return public_ip

def spot(symbol: str):
    return 'spot_'+symbol
def swapU(symbol: str):                 #u本位
    return 'swap_'+symbol+':USDT'
def swapC(symbol: str):                 #币本位永续
    return 'delivery_'+symbol+'/USD:'+ symbol
def futureU(symbol: str, timeIndex = 0):#交割合约,币种结算时间排序,0是最近
    return f'future_{symbol}-{timeIndex}'
def futureC(symbol: str,  timeIndex = 0):#币本位交割合约
    return swapC(symbol) + f'-{timeIndex}'

# 绑定消息,类需实现def evtProcess(self, key, *args):
def evtConnect(strEvt, obj):
    def rtMsg(sender, **kwargs):
        event_args = kwargs.get('args', ())
        return obj.evtProcess(sender, *event_args)
    dispatcher.connect(rtMsg, signal=strEvt, weak=False)
    dispatcher.connect(rtMsg, signal=_evtTargetSignal(strEvt, obj.__class__.__name__), weak=False)

def _evtTargetSignal(strEvt: object, targetName: str) -> tuple[object, str]:
    return (strEvt, targetName)

# 发送消息 - 同步版本
def evtFire(strEvt, *args):
    responses = dispatcher.send(signal=strEvt, sender=strEvt, args=args)
    # 排除False: receiver的switchFn未命中时返回False,不是有效结果
    return next((r for _, r in responses if r is not None and r is not False), None)

# 发送消息 - 指定监听类返回
def evtReturn(strEvt: object, targetName: str, *args: object) -> Any:
    responses = dispatcher.send(signal=_evtTargetSignal(strEvt, targetName), sender=strEvt, args=args)
    return next((r for _, r in responses if r is not None and r is not False), None)

# 发送消息 - 无返回值版本,单个receiver抛异常不影响其余receiver
# 必须在事件循环线程内调用: 所有evtProcess都是纯内存操作,丢线程池会让storage状态被多线程读写并打乱事件顺序
def evtFireAsync(strEvt, *args):
    for receiver in list(dispatcher.getAllReceivers(sender=dispatcher.Any, signal=strEvt)):
        try:
            receiver(sender=strEvt, args=args)
        except Exception as e:
            print(f"❌ [事件错误] 信号: {strEvt} -> 回调: {getattr(receiver, '__name__', receiver)} 执行失败: {e}")
            traceback.print_exc()

# 同步函数丢线程池执行,不阻塞事件循环: obj须持有 _executor(ThreadPoolExecutor)
async def threadCall(obj, fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(obj._executor, partial(fn, *args, **kwargs))

# 返回文件后缀
def getFileExtension(fileName):
    name, extension = os.path.splitext(fileName)
    return extension[1:], name

# 时间转换
def str2ms(strTime: str, utc=0):
    return int(str2time(strTime, utc).timestamp() * 1000)

def str2time(strTime: str, utc=0):
    def now():
        return datetime.now()
    def pre():
        return reviseTime('now', -5 * int(eTimeTs['m']))
    def strNow():
        return now().strftime('%Y-%m-%d %H:%M:%S')

    rt = strTime # 时间格式不转化
    if not isinstance(strTime, datetime):
        rt = switchFn({"now": now, "pre5": pre, 'strNow': strNow}, key=strTime) \
             or datetime.strptime(strTime, '%Y-%m-%d %H:%M:%S')

    #添加时区
    reversed_utc = -utc
    return (rt + timedelta(hours=reversed_utc)) if reversed_utc else rt

# 修正时间，+-(秒)
def reviseTime(strTime, sconds):
    return str2time(strTime) + timedelta(seconds=sconds)

# 时间差
def diff_Pdtime(pdBegin: pd.Timestamp, endTime: str | pd.Timestamp = 'now') -> float:
    if endTime == 'now':
        endTs = pd.Timestamp.now() - pd.Timedelta(hours=utc_now())
    else:
        endTs = pd.to_datetime(endTime, format="%Y-%m-%d %H:%M:%S")
        if isinstance(endTime, str):
            endTs -= pd.Timedelta(hours=utc_now())
    return (endTs - pdBegin).total_seconds()

# str，替换
def strReplace(symbolName, strRep=('/', '-')):
    return symbolName.replace(strRep[0], strRep[1])
#字符串分割
def split_by(src: str, sep: str) -> list[str]:
    return [s.strip() for s in src.split(sep)]
def slit(src, target):
    parts = src.split(target)
    if len(parts) > 1:
        return parts[0], parts[1]
    return False

# find
def lfind(lists, key, target):
    return listFind(lists, lambda item: item[key] == target)
def listFind(lists, fnJudge):
    return next((item for item in lists if fnJudge(item)), None)
def dictFind(d, fnJudge):
    return next(((k, v) for k, v in d.items() if fnJudge(k, v)), None)

def aContainB(src, strOrTab):
    return any(strKey in src for strKey in strOrTab)

# 分支调用,如不存在触发default
def switch(dice, key: str):
    return dice.get(key) or dice.get('default') or False
def switchFn(diceFn, key: str, **kwargs):
    fn = diceFn.get(key) or diceFn.get('default')
    return fn(**kwargs) if fn else False
def trySwitchFn(diceFn, key, **kwargs):
    return tryCatch(lambda: switchFn(diceFn, key, **kwargs))
# 若key1在dice里存在返回key1，否则返回key2
def switchV(dice, key1, key2):
    return dice.get(key1) or dice.get(key2)

#全局tryCatch,方便使用捕抓崩溃
isTry = False
def tryCatch(fn):
    if not isTry:
        return fn()
    try:
        return fn()
    except Exception as e:
        # err("错误:", e)
        print("~错误~",e)

def timeFrame2Float(timeframe):
    return float(timeframe[:-1]) * eTimeTs[timeframe[-1]]
def sec2min(seconds):
    minutes = seconds // 60
    return minutes
def utc_now():
    local_now = datetime.now().astimezone()
    utc_offset_seconds = local_now.utcoffset().total_seconds()
    return int(utc_offset_seconds / 3600)

# 搜索路径下的文件
def path2File(path, fileType=''):
    try:
        items = os.listdir(path)
        files = [item for item in items
            if os.path.isfile(os.path.join(path, item))
            and item.endswith(fileType)]
        return files
    except Exception as e:
        print(e)
    return []
# 当前文件的工作路径
def curPath():
    caller_frame = inspect.stack()[1]
    caller_file = caller_frame.filename
    return os.path.dirname(os.path.realpath(caller_file)) + '/'
# 加载路径
def joinPath(path, fileName):
    return path + fileName

def getRootName(cls, rootDir: str) -> str:
    try:
        # 获取传入类所在的文件
        strategy_file = Path(inspect.getfile(cls))
        # 向上查找指定的基目录并返回其下一级目录名
        parent = next((p for p in strategy_file.parents if p.name == rootDir), None)
        return strategy_file.relative_to(parent).parts[0] if parent else ''
    except (TypeError, OSError):
        return ''

# 生成带时间后缀的文件名: path/{suffix}.{ext}
def genFileName(path: str, file_split: str, ext: str) -> str:
    fmt = {'Y': '%Y', 'D': '%Y-%m-%d'}.get(file_split, '')
    suffix = datetime.now().strftime(fmt) if fmt else ''
    name = f"{suffix}.{ext}" if suffix else f"data.{ext}"
    return joinPath(path, name)
# 文件操作
def readFile(pathFile, model='r'):
    if not os.path.isfile(pathFile):  #检测文件是否存在(isfile对不存在的路径也返回False)
        return None
    fileType, _ = getFileExtension(pathFile)
    def _json():
        with open(pathFile, model, encoding='utf-8') as f:
            return json.load(f)
    def _jsonl():
        with open(pathFile, model, encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]
    def _pkl():
        with open(pathFile, 'rb') as f:
            return pickle.load(f)
    def _txt():
        with open(pathFile, model, encoding='utf-8') as f:
            return f.read()
    def _gz():
        with gzip.open(pathFile, 'rb') as f:
            return pickle.load(f)
    def _h5():
        with pd.HDFStore(pathFile, model) as store:
            return {key: store[key] for key in store.keys()}
    def _xlsx():
        return pd.read_excel(pathFile, engine='openpyxl')
    def _parquet():
        return pd.read_parquet(pathFile, engine='pyarrow')
    def _csv():
        return pd.read_csv(pathFile)
    return switchFn({
        'json': _json,
        'jsonl': _jsonl,
        'pkl': _pkl,
        'txt': _txt,
        'gz': _gz,
        'h5': _h5,
        'xlsx': _xlsx,
        'parquet': _parquet,
        'csv': _csv
    }, key=fileType)
def writeFile(data, pathFile, model='w'):
    if data is None or (isinstance(data, (list, dict)) and len(data) == 0):
        return False
    fileType, _ = getFileExtension(pathFile)
    def _json():
        with open(pathFile, model, encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    def _jsonl():
        with open(pathFile, model, encoding='utf-8') as f:
            for record in data:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
    def _pkl():
        with open(pathFile, 'wb') as f:
            pickle.dump(data, f)
    def _txt():
        with open(pathFile, model, encoding='utf-8') as f:
            f.write(str(data))
    def _gz():
        with gzip.open(pathFile, 'wb') as f:
            pickle.dump(data, f)
    def _h5():
        with pd.HDFStore(pathFile, model) as store:
            if isinstance(data, dict):
                for key, value in data.items():
                    store.put(key, value)
            else:
                store.put('data', data)
    def _xlsx():
        if isinstance(data, dict):
            with pd.ExcelWriter(pathFile) as writer:
                for key, value in data.items():
                    value.to_excel(writer, engine='openpyxl', index=False)
        else:
            data.to_excel(pathFile, engine='openpyxl', index=False)
    def _parquet():
        data.to_parquet(pathFile, engine='pyarrow', compression='snappy')
    def _csv():
        data.to_csv(pathFile, index=False)
    result = switchFn({
        'json': _json,
        'jsonl': _jsonl,
        'pkl': _pkl,
        'txt': _txt,
        'gz': _gz,
        'h5': _h5,
        'xlsx': _xlsx,
        'parquet': _parquet,
        'csv': _csv
    }, key=fileType)
    # switchFn 找不到对应文件类型时返回 False,否则(即便回调无显式返回值/None)视为成功
    return result is not False

# 防抖异步落盘: 多次调用只在最后一次后延迟 delaySec 秒执行一次 saveFn(同步函数,内部丢线程池跑,不阻塞事件循环)
def debouncedSaver(delaySec: float, saveFn):
    state = {'pending': False}
    async def _later():
        try:
            await asyncio.sleep(delaySec)
            await asyncio.to_thread(saveFn)
        finally:
            state['pending'] = False
    def request():
        if state['pending']:
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            saveFn()   # 同步启动阶段(事件循环还没起来),没有循环可以丢任务,直接同步保存
            return
        state['pending'] = True
        state['task'] = asyncio.create_task(_later())  # 持强引用,避免task被GC回收
    return request

# 加载
def require(modPath):
    mod = import_module(modPath)
    className = modPath.rsplit('.', 1)[-1]
    obj = getattr(mod, className, None)
    if obj is None:
        print(className, "类创建失败，请检查路径", mod)
    return obj

def openWeb(page=0):
    evtFire(kEvt_Web, 10, page)
    url = 'http://localhost:5173/'
    browser = webbrowser.get('safari') if sys.platform.startswith("darwin") else webbrowser
    browser.open(url)

#转换成web支持的格式
def rtWeb(data: dict) -> dict[str, Any]:
    def _convertValue(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: _convertValue(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_convertValue(item) for item in value]
        if value is pd.NA or value is pd.NaT:
            return None
        if isinstance(value, pd.Timestamp):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, np.datetime64):
            return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, (datetime, date)):
            return value.strftime("%Y-%m-%d %H:%M:%S") if isinstance(value, datetime) else value.isoformat()
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            value = float(value)
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return value

    def _convertKline(pf: pd.DataFrame) -> list[dict[str, Any]]:
        if pf is None or pf.empty:
            return []
        web_pf = pf.copy()
        if "candle_begin_time" in web_pf.columns:
            time_col = pd.to_datetime(web_pf["candle_begin_time"], errors="coerce")
            if isinstance(time_col.dtype, pd.DatetimeTZDtype):
                # get() may return timezone-aware local timestamps; epoch is always UTC.
                time_col = time_col.dt.tz_convert('UTC')
            elif web_pf.attrs.get('pdData_time_basis') == 'local':
                # A legacy/naive local copy needs the local offset removed before
                # serializing the instant as a UTC epoch.
                time_col -= pd.Timedelta(hours=utc_now())
            web_pf["time"] = [int(t.value // 1_000_000_000) if pd.notna(t) else None for t in time_col]
            web_pf.drop(columns=["candle_begin_time"], inplace=True)
        if "vol" in web_pf.columns and "volume" not in web_pf.columns:
            web_pf.rename(columns={"vol": "volume"}, inplace=True)
        return _convertValue(web_pf.to_dict(orient="records"))

    return {
        key: _convertKline(val) if isinstance(val, pd.DataFrame) else _convertValue(val)
        for key, val in data.items()
    }
# 并行
# def pool(fnCall, valueList, count = 2):
#     with Pool(processes=count) as pool:
#         return pool.map(fnCall, valueList)
