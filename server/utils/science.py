import math,time,random,ta
import pandas as pd
from decimal import Decimal, ROUND_UP
# from server.utils.common import switchFn
# from server.market.consts import kLong,kShort,kBuy,kSell

import numpy as np

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
def contractProfit(openPrice, closePrice, quantity):
    return (float(closePrice) - float(openPrice)) * quantity

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

def trend(pf, mode='all'):
    df = pf.copy()
    _empty = lambda: {'bull': None, 'bear': None, 'range': (int(df.index[0]), int(df.index[-1]))} if mode == 'last' \
        else {'bull': [], 'bear': [], 'range': [(int(df.index[0]), int(df.index[-1]))]}

    if len(df) < 5:
        return _empty()

    # ---------- 1. Swing High/Low 检测（顶只看high，底只看low）----------
    N = 2
    h, l = df['high'], df['low']
    swing_high = pd.Series(True, index=df.index)
    swing_low = pd.Series(True, index=df.index)
    for j in range(1, N + 1):
        swing_high &= (h > h.shift(j)) & (h > h.shift(-j))
        swing_low  &= (l < l.shift(j)) & (l < l.shift(-j))

    # ---------- 2. 收集分型点并排序 ----------
    fx = []
    for idx in df.index:
        if swing_high.iloc[idx]:
            fx.append((idx, 'top', h.iloc[idx]))
        if swing_low.iloc[idx]:
            fx.append((idx, 'bottom', l.iloc[idx]))
    fx.sort(key=lambda x: x[0])

    if len(fx) < 2:
        return _empty()

    # ---------- 3. 强制交替序列（连续同类型保留更极端的）----------
    pivots = [fx[0]]
    for i in range(1, len(fx)):
        last, curr = pivots[-1], fx[i]
        if curr[1] == last[1]:
            if (curr[1] == 'top' and curr[2] > last[2]) or \
               (curr[1] == 'bottom' and curr[2] < last[2]):
                pivots[-1] = curr
        else:
            pivots.append(curr)

    if len(pivots) < 4:
        return _empty()

    # ---------- 4. 趋势判断：pivots[i] vs pivots[i-2] 同类型比较 ----------
    # 交替序列中 pivots[i] 和 pivots[i-2] 一定同类型，恰好隔一个波段
    segments = []
    state_start = df.index[0]
    current_state = 'range'

    for i in range(3, len(pivots)):
        p_cur = pivots[i]
        p_prev_same = pivots[i - 2]    # 同类型
        p_other_cur = pivots[i - 1]    # 异类型
        p_other_prev = pivots[i - 3]   # 与 i-1 同类型

        if p_cur[1] == 'top':
            h_cur, h_prev = p_cur[2], p_prev_same[2]
            l_cur, l_prev = p_other_cur[2], p_other_prev[2]
        else:
            l_cur, l_prev = p_cur[2], p_prev_same[2]
            h_cur, h_prev = p_other_cur[2], p_other_prev[2]

        if h_cur > h_prev and l_cur > l_prev:
            new_state = 'bull'
        elif h_cur < h_prev and l_cur < l_prev:
            new_state = 'bear'
        else:
            new_state = 'range'

        if new_state != current_state:
            boundary = pivots[i - 1][0]
            segments.append((current_state, state_start, boundary))
            state_start = boundary
            current_state = new_state

    segments.append((current_state, state_start, df.index[-1]))

    # ---------- 5. 格式化输出 ----------
    result = {'bull': [], 'bear': [], 'range': []}
    for state, s, e in segments:
        result[state].append((int(s), int(e)))

    if mode == 'last':
        return {k: (result[k][-1] if result[k] else None) for k in ['bull', 'bear', 'range']}
    return result