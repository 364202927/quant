import math
import time
import random
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

# 浮盈
# def floating_PL(positionSide, entry, mark, amt):
    # 浮动亏损 = (开仓价 - 当前标记价格) * 合约数量（对于多头）
    # 浮动亏损 = (当前标记价格 - 开仓价) * 合约数量（对于空头）
    # 浮动亏损百分比 = (浮动亏损 / 初始保证金) * 100
    # pass

# 检测单一k线形态


def patternType(pd, type):
    def bullish():  # 阳线
        return pd['close'] > pd['open']

    def bearish():  # 阴线
        return pd['close'] < pd['open']

    def hammer():  # 锤子线
        real_body = abs(pd['close'] - pd['open'])
        lower_shadow = pd['open'] - \
            pd['low'] if pd['open'] < pd['close'] else pd['close'] - pd['low']
        upper_shadow = pd['high'] - \
            pd['close'] if pd['open'] < pd['close'] else pd['high'] - pd['open']
        return lower_shadow > 2 * real_body and upper_shadow < real_body

    def InvHammer():  # 倒锤子线
        real_body = abs(pd['close'] - pd['open'])
        lower_shadow = pd['open'] - \
            pd['low'] if pd['open'] < pd['close'] else pd['close'] - pd['low']
        upper_shadow = pd['high'] - \
            pd['close'] if pd['open'] < pd['close'] else pd['high'] - pd['open']
        return upper_shadow > 2 * real_body and lower_shadow < real_body
    return switchFn({'up': bullish,
                     'down': bearish},
                    key=type)

# 检测pf是否包含有标签


def labIsin(df, tabLab):
    labels = {col: i for i, col in enumerate(df.columns)}
    for label in tabLab:
        if not labels.get(label):
            return False
    return True

# k线是否交叉


def crossUp(index, targeMa, preMa):
    if targeMa.iloc[index] > preMa.iloc[index] and targeMa.iloc[index -
                                                                1] <= preMa.iloc[index - 1]:
        return True
    return False


def crossDown(index, targeMa, preMa):
    if targeMa.iloc[index] < preMa.iloc[index] and targeMa.iloc[index -
                                                                1] >= preMa.iloc[index - 1]:
        return True
    return False

# 合约收益


def contractProfit(openPrice, closePrice, amount):
    return (float(closePrice) - float(openPrice)) * amount

# 计算浮动盈利


def floatingProfit(openPrice, closePrice, dir):
    if dir == 'LONG':
        return (closePrice - openPrice) / openPrice * 100
    return (openPrice - closePrice) / openPrice * 100
