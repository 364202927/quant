import pickle,json,datetime,time,os,requests,inspect,asyncio,inspect
from importlib import import_module
from pydispatch import dispatcher
from server.utils import eTimeTs
import pandas as pd


savePath = "data/save/"

def publicIp():
    response = requests.get('https://api.ipify.org?format=json')
    public_ip = response.json()['ip']
    return public_ip


# 绑定消息
def evtConnect(strEvt, obj):
    def rtMsg(sender, value, value1, value2, value3):
        obj.evtProcess(sender, value, value1, value2, value3)
    dispatcher.connect(rtMsg, signal=strEvt, weak=False)


# 发送消息(最多3参数) - 同步版本
def evtFire(strEvt, *args):
    def getValue(index):
        if index < len(args):
            return args[index]
        return ''
    dispatcher.send(signal=strEvt, sender=strEvt, 
                    value=getValue(0), value1=getValue(1),
                    value2=getValue(2), value3=getValue(3))


# 发送消息(最多3参数) - 异步版本
async def evtFireAsync(strEvt, *args):
    def getValue(index):
        return args[index] if index < len(args) else ''
    
    # 获取所有监听者
    receivers = dispatcher.getAllReceivers(sender=dispatcher.Any, signal=strEvt)
    if not receivers:
        return
    
    # 并发执行所有回调
    tasks = []
    for receiver in receivers:
        try:
            if inspect.iscoroutinefunction(receiver):# 异步回调：创建task
                task = receiver(
                    sender=strEvt,
                    value=getValue(0),
                    value1=getValue(1),
                    value2=getValue(2),
                    value3=getValue(3))
                tasks.append(task)
            else:# 同步回调
                receiver(
                    sender=strEvt,
                    value=getValue(0),
                    value1=getValue(1),
                    value2=getValue(2),
                    value3=getValue(3))
        except Exception as e:
            print(f"事件回调执行失败: {strEvt}, 错误: {e}")
    
    # 等待所有异步任务完成
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


# 加载json
def loadJson(filePath):
    with open(filePath, "r", encoding="utf-8") as file:
        fileData = json.load(file)
    return fileData

# 加载路径
def joinPath(path, fileName):
    fullPath = path + fileName
    return fullPath


def readFile(path, fileType):
    pass


# 返回文件后缀
def getFileExtension(fileName):
    name, extension = os.path.splitext(fileName)
    return extension[1:], name


# 时间转换
def str2ms(strTime: str, utc=0):
    date = str2time(strTime)
    if utc > 0:
        date += datetime.timedelta(hours=utc)
    return int(date.timestamp() * 1000)


def str2time(strTime: str):
    def now():
        return datetime.datetime.now()

    def pre():
        time_val = 5 * int(eTimeTs['m'])
        return reviseTime('now', -time_val)

    if isinstance(strTime, datetime.datetime):  # 时间直接返回
        return strTime
    rt = switchFn({"now": now, "pre5": pre}, key=strTime)
    if not rt:
        return datetime.datetime.strptime(strTime, '%Y-%m-%d %H:%M:%S')
    return rt


# 修正时间，+-(秒)
def reviseTime(strTime, sconds):
    date = str2time(strTime)
    if sconds > 0:
        return date + datetime.timedelta(seconds=abs(sconds))
    return date - datetime.timedelta(seconds=abs(sconds))


# 时间差
def diff_Pdtime(pdTime, seconds='now'):
    seconds = pd.Timestamp.now() if seconds == 'now' else seconds
    return abs((seconds - pdTime).total_seconds() / 60)
    

# str
def strReplace(symbolName, strRep=['/', '-']):
    return symbolName.replace(strRep[0], strRep[1])


def slit(src, target):
    parts = src.split(target)
    if len(parts) > 1:
        return parts[0], parts[1]
    return False


def aContainB(input, strOrTab):
    for strKey in strOrTab:
        if strKey in input:
            return True
    return False


# find
def lfind(lists, key, target):
    # for item in iter(lists):
    #     if item[key] == target:
    #         return item
    # return None
    def compare(item):
        return item[key] == target
    return fnfind(lists, compare)


def fnfind(lists, fnJudge):
    for item in iter(lists):
        if fnJudge(item):
            return item
    return None


# 分支调用
def switch(dice, key):
    if not dice.get(key):
        # print("err：找不到key", dice, key)
        return False
    return dice.get(key)


def switchFn(diceFn, key, **kwargs):
    if not diceFn.get(key):
        # print("switchFn err 没有接收函数", key, diceFn)
        return False
    return diceFn[key](**kwargs)


def trySwitchFn(diceFn, key, attempts, **kwargs):
    rt = switchFn(diceFn, key, **kwargs)
    return True, rt
    ####
    # for i in range(attempts):
    #     try:
    #         rt = switchFn(diceFn, key, **kwargs)
    #         return True, rt
    #     except Exception as e:
    #         time.sleep(0.1)
    # return False, strErr


def tryExecution(fn, attempts=3, sleepTime=0.2):
    for i in range(attempts):
        try:
            return True, fn()
        except Exception:
            time.sleep(sleepTime)
    return False, None


# 若key1在dice里存在返回key1，否则返回key2
def switchV(dice, key1, key2):
    return dice.get(key1) and dice.get(key1) or dice.get(key2)


def timeFrame2int(timeframe):
    # keyTime = int(timeframe[:-1]) * eTimeTs[timeframe[-1]]
    # return int(eTimeTs[timeframe])
    return int(timeframe[:-1]) * eTimeTs[timeframe[-1]]


def sec2min(seconds):
    minutes = seconds // 60
    return minutes


# 搜索路径下的文件
def path2File(path, fileType=''):
    try:
        items = os.listdir(path)
        files = [
            item for item in items
            if os.path.isfile(os.path.join(path, item))
            and item.endswith(fileType)
        ]
        return files
    except Exception as e:
        print(e)
    return []


# 当前文件的工作路径
def curPath():
    caller_frame = inspect.stack()[1]
    caller_file = caller_frame.filename
    return os.path.dirname(os.path.realpath(caller_file)) + '/'


# 加载
def require(modPath):
    mod = import_module(modPath)
    className = modPath[modPath.rfind('.') + 1:]
    try:
        obj = getattr(mod, className)
    except AttributeError:
        print(className, "类创建失败，请检查路径", mod)
    return obj


def pd2File(dict, filePath):
        # ata_dict = {
        #     'df1': pd.DataFrame({'A': [1, 2], 'B': ['x', 'y']}),
        #     'df2': pd.DataFrame({'C': [3.0, 4.0], 'D': [True, False]}),
        #     # ... 其他df3, df4, df5
        # }
        # # 方法1：保存为pickle文件
        # with open('combined_data.pkl', 'wb') as f:
        #     pickle.dump(data_dict, f)
        # # 方法2：保存为joblib文件（适合大数据）
        # dump(data_dict, 'combined_data.joblib')
        # # 读取时
        # with open('combined_data.pkl', 'rb') as f:
        #     loaded_dict = pickle.load(f)
        # h5
        # with pd.HDFStore('combined_data.h5') as store:
        #     store.put('df1', data_dict['df1'])
        #     store.put('df2', data_dict['df2'])
        #     # ... 其他DF
        # # 读取时
        # with pd.HDFStore('combined_data.h5') as store:
        #     df1 = store.get('df1')
        #     df2 = store.get('df2')
    # xlsx
        # with pd.ExcelWriter('combined_data.xlsx') as writer:
        #     data_dict['df1'].to_excel(writer, sheet_name='df1')
        #     data_dict['df2'].to_excel(writer, sheet_name='df2')
        #     # ... 其他DF
        # # 读取时
        # df1 = pd.read_excel('combined_data.xlsx', sheet_name='df1')
        # df2 = pd.read_excel('combined_data.xlsx', sheet_name='df2')
    _, fileType = slit(filePath, '.')
    path = savePath + filePath

    def pkl():
        with open(path, 'wb') as f:
            pickle.dump(dict, f)

    def h5():  # todo:未完成
        with pd.HDFStore(path) as store:
            for key, value in dict.items():
                store.put(key, value)
    #     store.put('df2', data_dict['df2'])

    def xlsx():  # todo:未完成
        with pd.ExcelWriter(path) as writer:
            for key, value in dict.items():
                dict[key].to_excel(writer, sheet_name=value)

    switchFn({'pkl': pkl, 'h5': h5, 'xlsx': xlsx}, key=fileType)


def loadPdFile(fileName):
    _, fileType = slit(fileName, '.')
    path = "data/save/" + fileName

    def pkl():
        with open(path, 'rb') as f:
            return pickle.load(f)

    def h5():  # todo:未完成
        with pd.HDFStore(path) as store:
            for key, value in dict.items():
                store.put(key, value)
    #     store.put('df2', data_dict['df2'])

    def xlsx():  # todo:未完成
        with pd.ExcelWriter(path) as writer:
            for key, value in dict.items():
                dict[key].to_excel(writer, sheet_name=value)

    return switchFn({'pkl': pkl, 'h5': h5, 'xlsx': xlsx}, key=fileType)


# 并行
# def pool(fnCall, valueList, count = 2):
#     with Pool(processes=count) as pool:
#         return pool.map(fnCall, valueList)
