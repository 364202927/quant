from server.utils.fileConfig import g_config
import inspect
import pprint

kErr = 999
kWarn = 888
kInfo = 777
kLogln = 666


def printInfo(*args, lv=1, isSaveFile=False):
    if g_config.logger()['level'] >= lv:
        return
    strInfo = 'log('
    callName = ''
    if lv == kErr:
        strInfo = 'error('
    elif lv == kWarn:
        strInfo = 'warn('
    # 打印调用函数
    if lv <= kErr:
        callName = inspect.stack()[2].function
    str_normal = '):'
    if lv == kLogln:
        str_normal = '):\n'
    print(strInfo + callName + str_normal, *args)
    # todo:记录log到文件


def log(*args, isSaveFile=False):
    printInfo(*args, lv=kInfo, isSaveFile=isSaveFile)


def logln(*args, isSaveFile=False):
    printInfo(*args, lv=kLogln, isSaveFile=isSaveFile)


def logFormat(value):
    # if isinstance(value, dict):
    #     json_str = json.dumps(value, indent=4)
    #     # print("info:格式化输出\n",json_str)
    #     print(json_str)
    # else:
    #     print(value)
    pprint.pprint(value)


def err(*args, isSaveFile=True):
    printInfo(*args, lv=kErr, isSaveFile=isSaveFile)
    exit()  # todo:先暂时这样处理


def warn(*args, isSaveFile=False):
    printInfo(*args, lv=kWarn, isSaveFile=isSaveFile)
