import json,datetime,time,os
from importlib import import_module
from pydispatch import dispatcher
from utils.enumeration import timeTs
# from multiprocessing.pool import Pool

#绑定消息
def evtConnect(strEvt, obj):
    def rtMsg(sender, value, value1, value2, value3):
        obj.evtProcess(sender, value, value1, value2, value3)
    dispatcher.connect(rtMsg, signal=strEvt,weak=False)
#发送消息
def evtFire(strEvt, *args):
    def getValue(index):
        if index < len(args):
            return args[index]
        return ''
    dispatcher.send(signal=strEvt, sender=strEvt, 
                    value = getValue(0), value1 = getValue(1),value2 = getValue(2),value3 = getValue(3))

def loadJson(filePath):
    with open(filePath, "r") as file:
        fileData = json.load(file)
    return fileData

def joinPath(path, fileName):
    newPath = os.path.join(path)
    fullPath = path + fileName
    return fullPath

def readFile(path, fileType):
    pass

def getFileExtension(fileName):
    _, extension = os.path.splitext(fileName)
    return extension[1:]

def str2ms(strTime: str, utc = 0):
    if strTime == "now":
        date = datetime.datetime.now()
    else:
        date = str2time(strTime)#datetime.datetime.strptime(strTime, "%Y-%m-%d %H:%M:%S")
    if utc > 0:
        date += datetime.timedelta(hours=utc)
    return int(date.timestamp() * 1000)

def str2time(strTime: str):
    return datetime.datetime.strptime(strTime, '%Y-%m-%d %H:%M:%S')
        
# def timeConvert(pdTime, toStr=False):
#     day = pdTime.days
#     seconds = pdTime.seconds
#     hours = seconds//3600
#     if toStr:
#         return str(day)+"天"+str(hours)+"时"+str((seconds - hours*3600)//60)+"分"
#     return day, hours, (seconds - hours*3600)//60

# def iso2Time(dataTime: str):
#     newTime = dataTime[:-5]
#     return newTime.replace('T', ' ')

# def time2Iso(dataTime: str):
#     newTime = dataTime.replace(' ', 'T')
#     return newTime + "Z"

# def midReplace(symbolName: str):
#     return symbolName.replace('/', '-')


# def timeReplace(time1: str, time2: str) ->str:
#     def replace(time):
#         return time.replace('-', '')[:8]
#     return replace(time1) + "~"+replace(time2)

# def isDapi(symbolName: str):
    # return (symbolName.endswith('_PERP') or symbolName.endswith('-SWAP'))

def timeFrame2int(timeframe):
    return int(timeTs[timeframe])

def sec2min(seconds):
    minutes = seconds // 60
    return minutes

# 搜索路径下的文件
def path2File(path, fileType):
    file_list = []
    strLen = len(fileType)
    for root, dirs, files in os.walk(path):
        for filename in files:
            if filename.endswith(fileType):
                file_path = os.path.join(root, filename)
                file_path = os.path.abspath(file_path)
                file_list.append(
                    {'name': filename[:-strLen], 'path': file_path})
    return file_list

#加载
def require(modPath):
    mod = import_module(modPath)
    className = modPath[modPath.rfind('.') + 1:]

    try:
        obj = getattr(mod, className)
    except AttributeError:
        print(className, "类创建失败，请检查路径", mod)
    return obj

# 并行
# def pool(fnCall, valueList, count = 2):
#     with Pool(processes=count) as pool:
#         return pool.map(fnCall, valueList)
