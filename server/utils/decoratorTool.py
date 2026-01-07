import time

# 单例


def singleton(cls):
    instances = {}

    def wrapper(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return wrapper

# 计算函数调用时间


def fun_calc(func):
    def wrapper(*args, **kargs):
        startTime = time.time()
        f = func(*args, **kargs)
        exec_time = time.time() - startTime
        print("函数总计时间：", exec_time)
        return f
    return wrapper
