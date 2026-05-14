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
    
    # ---------- 1. 严格顶底分型（4根K线确认，高低点同时满足）----------
    top = (
        (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(-1)) &
        (df['high'] > df['high'].shift(2)) & (df['high'] > df['high'].shift(-2)) &
        (df['low'] > df['low'].shift(1)) & (df['low'] > df['low'].shift(-1)) &
        (df['low'] > df['low'].shift(2)) & (df['low'] > df['low'].shift(-2))
    )
    bottom = (
        (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(-1)) &
        (df['low'] < df['low'].shift(2)) & (df['low'] < df['low'].shift(-2)) &
        (df['high'] < df['high'].shift(1)) & (df['high'] < df['high'].shift(-1)) &
        (df['high'] < df['high'].shift(2)) & (df['high'] < df['high'].shift(-2))
    )
    
    # 收集分型（索引，类型，极值价格）
    fx = []
    for idx in df.index:
        if top.loc[idx]:
            fx.append((idx, 'top', df['high'].loc[idx]))
        elif bottom.loc[idx]:
            fx.append((idx, 'bottom', df['low'].loc[idx]))
    
    if len(fx) < 2:
        seg = (df.index[0], df.index[-1])
        if mode == 'last':
            return {'bull': None, 'bear': None, 'range': seg}
        return {'bull': [], 'bear': [], 'range': [seg]}
    
    # ---------- 2. 生成严格交替的转折点序列 ----------
    # 去除连续同类型分型，只保留交替序列中更极端的那个
    pivots = [fx[0]]
    for i in range(1, len(fx)):
        last = pivots[-1]
        curr = fx[i]
        if curr[1] == last[1]:  # 同类型
            # 保留更极端的：顶取更高，底取更低
            if curr[1] == 'top' and curr[2] > last[2]:
                pivots[-1] = curr
            elif curr[1] == 'bottom' and curr[2] < last[2]:
                pivots[-1] = curr
        else:
            pivots.append(curr)
    
    if len(pivots) < 2:
        seg = (df.index[0], df.index[-1])
        if mode == 'last':
            return {'bull': None, 'bear': None, 'range': seg}
        return {'bull': [], 'bear': [], 'range': [seg]}
    
    # ---------- 3. 根据转折点序列划分趋势状态 ----------
    # 状态判定规则：
    # - 牛市：最近两个底抬升，且最近两个顶也抬升（需至少2底2顶）
    # - 熊市：最近两个底降低，且最近两个顶也降低
    # - 否则为震荡
    # 我们逐个转折点推进，维护最近的两个顶和两个底，动态判断。
    
    tops = []     # 记录顶点的 (索引, 价格)
    bottoms = []  # 记录底点的 (索引, 价格)
    # 每个转折点都会产生一个新的区间状态，我们累积同状态区间
    segments = []  # (state, start_idx, end_idx)
    current_state = None
    state_start = pivots[0][0]
    
    for i, p in enumerate(pivots):
        idx, ptype, price = p
        if ptype == 'top':
            tops.append((idx, price))
            # 保持只保留最近两个顶（但为了判断我们其实只需要最近两个，可以裁剪）
            if len(tops) > 2:
                tops.pop(0)
        else:
            bottoms.append((idx, price))
            if len(bottoms) > 2:
                bottoms.pop(0)
        
        # 当拥有至少两个顶和两个底时，可以判定趋势
        if len(tops) >= 2 and len(bottoms) >= 2:
            # 最近两个顶：tops[-2], tops[-1]；最近两个底同理
            high_prev, high_cur = tops[-2][1], tops[-1][1]
            low_prev, low_cur = bottoms[-2][1], bottoms[-1][1]
            
            if high_cur > high_prev and low_cur > low_prev:
                new_state = 'bull'
            elif high_cur < high_prev and low_cur < low_prev:
                new_state = 'bear'
            else:
                new_state = 'range'
        else:
            # 信息不足，暂时归为震荡（等待更多转折点）
            new_state = 'range'
        
        # 管理区间合并
        if current_state is None:
            current_state = new_state
            state_start = idx
        elif new_state != current_state:
            # 状态切换，前一个状态结束于上一个转折点
            # 但这里我们应以“上一个转折点”作为结束，而不是当前转折点
            prev_idx = pivots[i-1][0]
            segments.append((current_state, state_start, prev_idx))
            current_state = new_state
            state_start = prev_idx  # 新区间从上一个转折点开始
        # 如果状态相同，则继续延伸，不操作
    
    # 最后一段
    if current_state is not None:
        segments.append((current_state, state_start, pivots[-1][0]))
    
    # ---------- 4. 映射到原始K线范围 ----------
    result = {'bull': [], 'bear': [], 'range': []}
    for state, s_idx, e_idx in segments:
        mask = (df.index >= s_idx) & (df.index <= e_idx)
        sub = df.loc[mask]
        if len(sub) == 0:
            continue
        real_start = sub.index[0]
        real_end = sub.index[-1]
        result[state].append((int(real_start), int(real_end)))
    
    if mode == 'last':
        res = {}
        for k in ['bull', 'bear', 'range']:
            if result[k]:
                res[k] = result[k][-1]
            else:
                res[k] = None
        return res
    return result