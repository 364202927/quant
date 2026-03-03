import math,time,random
from decimal import Decimal, ROUND_UP
from server.utils.common import switchFn

# 是否落在范围
def inRange(range, num):
    min = range[0] is None and 0 or float(range[0])
    max = range[1] is None and math.inf or float(range[1])
    return min <= float(num) <= max

# def percentage(total, strPercentage):
#     if strPercentage.endswith('%'):
#             percentage = float(strPercentage[:-1])
#             # result = (percentage / 100) * value
#             return (percentage * 0.01) * strPercentage
#     return total

# 根据当前时间返回id
def time2ID():
    return f"{int(time.time())}{random.randint(1, 10000)}"

# 返回币安用的时间
def binanceTimestamp():
    return int(time.time() * 1000)

# 检测pf是否包含有标签
def labIsin(df, tabLab):
    labels = {col: i for i, col in enumerate(df.columns)}
    for label in tabLab:
        if not labels.get(label):
            return False
    return True

# 合约收益
def contractProfit(openPrice, closePrice, amount):
    return (float(closePrice) - float(openPrice)) * amount

# 计算浮动盈利
def floatingProfit(openPrice, closePrice, dir):
    if dir == 'LONG':
        return (closePrice - openPrice) / openPrice * 100
    return (openPrice - closePrice) / openPrice * 100
#除出来的结果会比a稍微大一点,精确到3位小数
def division(a:float, b:float, step = 0, precision:str = '0.001'):
    if b == 0:
        return
    raw_quantity = Decimal(a) / Decimal(b)
    num = float(raw_quantity.quantize(Decimal(precision), rounding=ROUND_UP))  # （强制向上进位）
    if step > 0:
        num = math.ceil(num / step) * step
    return num

# 浮盈
# def floating_PL(positionSide, entry, mark, amt):
    # 浮动亏损 = (开仓价 - 当前标记价格) * 合约数量（对于多头）
    # 浮动亏损 = (当前标记价格 - 开仓价) * 合约数量（对于空头）
    # 浮动亏损百分比 = (浮动亏损 / 初始保证金) * 100
    # pass