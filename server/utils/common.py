import pickle,json,time,os,requests,inspect,asyncio,inspect,gzip,webbrowser,sys,math
from importlib import import_module
from pydispatch import dispatcher
from server.utils import eTimeTs,kEvt_Web
from datetime import datetime, timezone, date, timedelta
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
# 发送消息 - 同步版本
def evtFire(strEvt, *args):
    responses = dispatcher.send(signal=strEvt, sender=strEvt, args=args)
    for _, result in responses:
        if result is not None:
            return result
    return None

# 发送消息 - 异步版本,没有返回值，自动判断事件循环
def evtFireAsync(strEvt, *args):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_evtFireAsync_impl(strEvt, *args))
    except RuntimeError:
        asyncio.run(_evtFireAsync_impl(strEvt, *args))

async def _evtFireAsync_impl(strEvt, *args):
    receivers = dispatcher.getAllReceivers(sender=dispatcher.Any, signal=strEvt)
    if not receivers:
        return

    tasks = []
    for receiver in receivers:
        kwargs = {"sender": strEvt, "args": args}
        if inspect.iscoroutinefunction(receiver):
            task = asyncio.create_task(receiver(**kwargs))
            tasks.append(task)
        else:
            task = asyncio.to_thread(receiver, **kwargs)
            tasks.append(task)

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for receiver, res in zip(receivers, results):
            if isinstance(res, Exception):
                func_name = getattr(receiver, '__name__', str(receiver))
                print(f"❌ [事件错误] 信号: {strEvt} -> 回调: {func_name} 执行失败: {res}")

# 返回文件后缀
def getFileExtension(fileName):
    name, extension = os.path.splitext(fileName)
    return extension[1:], name

# 时间转换
def str2ms(strTime: str, utc=0):
    date = str2time(strTime)
    reversed_utc = -utc 
    if reversed_utc != 0:
        date += timedelta(hours=reversed_utc)
    return int(date.timestamp() * 1000)

def str2time(strTime: str, utc=0):
    def now():
        return datetime.now()
    def pre():
        time_val = 5 * int(eTimeTs['m'])
        return reviseTime('now', -time_val)
    def strNow():
        return now().strftime('%Y-%m-%d %H:%M:%S')
    rt = strTime # 时间格式不转化
    if not isinstance(strTime, datetime):
        rt = switchFn({"now": now, "pre5": pre, 'strNow': strNow}, key=strTime)
        if not rt:
            rt = datetime.strptime(strTime, '%Y-%m-%d %H:%M:%S')
    #添加时区
    reversed_utc = -utc
    if reversed_utc != 0:
        rt += timedelta(hours=reversed_utc)
    return rt

# 修正时间，+-(秒)
def reviseTime(strTime, sconds):
    date = str2time(strTime)
    if sconds > 0:
        return date + timedelta(seconds=abs(sconds))
    return date - timedelta(seconds=abs(sconds))
# 时间差
def diff_Pdtime(pdBegin, endTime='now'):
    time = pd.Timestamp.now() if endTime == 'now' else pd.to_datetime(endTime,format="%Y-%m-%d %H:%M:%S")
    return (time - pdBegin).total_seconds()

# str，替换
def strReplace(symbolName, strRep=['/', '-']):
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
    # for item in iter(lists):
    #     if item[key] == target:
    #         return item
    # return None
    def compare(item):
        return item[key] == target
    return listFind(lists, compare)
def listFind(lists, fnJudge):
    for item in iter(lists):
        if fnJudge(item):
            return item
    return None
def dictFind(dict, fnJudge):
    for k, v in dict.items():
        if fnJudge(k,v):
            return k,v
    return None

def aContainB(input, strOrTab):
    for strKey in strOrTab:
        if strKey in input:
            return True
    return False

# 分支调用,如不存在触发default
def switch(dice, key:str):
    if not dice.get(key):
        if dice.get('default'):
            return dice['default']
        return False
    return dice.get(key)
def switchFn(diceFn, key:str, **kwargs):
    if not diceFn.get(key):
        if diceFn.get('default'):
            return diceFn['default'](**kwargs)
        return False
    return diceFn[key](**kwargs)
def trySwitchFn(diceFn, key, **kwargs):
    return tryCatch(switchFn(diceFn,key))
# 若key1在dice里存在返回key1，否则返回key2
def switchV(dice, key1, key2):
    return dice.get(key1) and dice.get(key1) or dice.get(key2)
#     rt = switchFn(diceFn, key, **kwargs)
#     return True, rt
    ####
    # for i in range(attempts):
    #     try:
    #         rt = switchFn(diceFn, key, **kwargs)
    #         return True, rt
    #     except Exception as e:
    #         time.sleep(0.1)
    # return False, strErr

#全局tryCatch,方便使用捕抓崩溃
isTry = False
def tryCatch(fn):
    if not isTry:
        return fn()
    try:
        return fn()
    except Exception as e:
        from server.utils import err
        err("错误:",e)

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
    fullPath = path + fileName
    return fullPath

def getRootName(cls, rootDir: str) -> str:
    try:
        # 获取传入类所在的文件
        strategy_file = Path(inspect.getfile(cls))
        # 向上查找指定的基目录并返回其下一级目录名
        for parent in strategy_file.parents:
            if parent.name == rootDir:
                return strategy_file.relative_to(parent).parts[0]
    except (TypeError, OSError):
        pass
    return ''
    
# 生成带时间后缀的文件名: path/{suffix}.{ext}
def genFileName(path: str, file_split: str, ext: str) -> str:
    fmt = {'Y': '%Y', 'D': '%Y-%m-%d'}.get(file_split, '')
    suffix = datetime.now().strftime(fmt) if fmt else ''
    name = f"{suffix}.{ext}" if suffix else f"data.{ext}"
    return joinPath(path, name)
# 文件操作
def readFile(pathFile,model = 'r'):
    if not os.path.exists(pathFile) or\
          not os.path.isfile(pathFile): #检测文件是否存在
        return None
    fileType, _ = getFileExtension(pathFile)
    def _json():
        with open(pathFile, model, encoding='utf-8') as f:
            return json.load(f)
    def _jsonl():
        with open(pathFile, model, encoding='utf-8') as f:
            return f
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
        return pd.read_excel(pathFile,  engine='openpyxl')
    def _parquet():
        return pd.read_parquet(pathFile, engine='pyarrow')
    def _csv():
        return pd.read_csv(pathFile)
    return switchFn({
        'json': _json,
        'jsonl':_jsonl,
        'pkl': _pkl,
        'txt': _txt,
        'gz': _gz,
        'h5': _h5,
        'xlsx': _xlsx,
        'parquet': _parquet,
        'csv': _csv
    }, key=fileType)
def writeFile(data, pathFile,model = 'w'):
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
        with pd.HDFStore(pathFile, 'w') as store:
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
        'jsonl':_jsonl,
        'pkl': _pkl,
        'txt': _txt,
        'gz': _gz,
        'h5': _h5,
        'xlsx': _xlsx,
        'parquet': _parquet,
        'csv': _csv
    }, key=fileType)

    # 如果 switchFn 返回 False（未找到对应的文件类型），返回 False，否则返回 True
    return result is not False

# 加载
def require(modPath):
    mod = import_module(modPath)
    className = modPath[modPath.rfind('.') + 1:]
    try:
        obj = getattr(mod, className)
    except AttributeError:
        print(className, "类创建失败，请检查路径", mod)
    return obj

def openWeb(page = 0):
        evtFire(kEvt_Web, 10, page)
        if sys.platform.startswith("darwin"):#macos
            safari = webbrowser.get('safari')
            safari.open('http://localhost:5173/')
            return
        webbrowser.open('http://localhost:5173/')
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
            web_pf["time"] = [int(t.timestamp()) if pd.notna(t) else None for t in time_col]
            web_pf.drop(columns=["candle_begin_time"], inplace=True)
        if "vol" in web_pf.columns and "volume" not in web_pf.columns:
            web_pf.rename(columns={"vol": "volume"}, inplace=True)
        return _convertValue(web_pf.to_dict(orient="records"))
    #return
    result = {}
    for key, val in data.items():
        if isinstance(val, pd.DataFrame):
            result[key] = _convertKline(val)
        else:
            result[key] = _convertValue(val)
    return result
# 并行
# def pool(fnCall, valueList, count = 2):
#     with Pool(processes=count) as pool:
#         return pool.map(fnCall, valueList)
