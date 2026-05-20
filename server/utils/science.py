import math,time,random,ta
import pandas as pd
from decimal import Decimal, ROUND_UP
# from server.utils.common import switchFn
# from server.market.consts import kLong,kShort,kBuy,kSell
# from hmmlearn import hmm

# import numpy as np

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


# todo暂时测试过周线有效
# 最简单的对策：优化方向
# 如果你想用更粗的指标来管理这个牛市，不用缠论那么精细。
# 用周线收盘价，配合周线MA20和趋势线。只要周线收盘价没有有效跌破MA20，或者没有跌破前一个波段的最低点（比如4.9万），你就可以坚定认为牛市还在继续。
def trend(pf, mode='all'):
    """
    基于长期均线斜率的牛/熊二元趋势识别。
    无震荡输出，自动适配日/周/月周期。
    """
    df = pf.copy()

    # ============ 0. 周期检测与参数设定 ============
    def detect_period(idx):
        if not isinstance(idx, pd.DatetimeIndex):
            return 'd'
        diffs = idx.to_series().diff().dropna()
        if len(diffs) == 0:
            return 'd'
        median_diff = diffs.median()
        days = median_diff / pd.Timedelta(days=1)
        if days <= 3:
            return 'd'
        elif days <= 10:
            return 'w'
        else:
            return 'm'

    period = detect_period(df.index)

    if period == 'd':
        ma_len = 60          # 长期均线周期
        slope_lookback = 10  # 斜率回溯期（用于判断方向）
        min_seg_len = 5      # 最小段合并长度
    elif period == 'w':
        ma_len = 26
        slope_lookback = 4
        min_seg_len = 2
    else:  # 月线
        ma_len = 12
        slope_lookback = 2
        min_seg_len = 1

    # ============ 1. 计算长期均线及其斜率 ============
    df['ma_long'] = df['close'].ewm(span=ma_len, adjust=False).mean()
    # 斜率简化：均线当前值 vs slope_lookback 前的值
    df['slope'] = df['ma_long'] - df['ma_long'].shift(slope_lookback)

    # ============ 2. 每日状态判定（忽略震荡，强制二元） ============
    def assign_state(row):
        if pd.isna(row['slope']):
            return None
        return 'bull' if row['slope'] > 0 else 'bear'

    df['state'] = df.apply(assign_state, axis=1)
    valid_df = df.dropna(subset=['state']).copy()

    if valid_df.empty:
        seg = (int(df.index[0]), int(df.index[-1]))
        if mode == 'last':
            return {'bull': None, 'bear': None, 'range': None}
        return {'bull': [], 'bear': [], 'range': []}

    # ============ 3. 原始分段 ============
    raw_segments = []
    start_idx = valid_df.index[0]
    current_state = valid_df['state'].iloc[0]
    for i in range(1, len(valid_df)):
        if valid_df['state'].iloc[i] != current_state:
            end_idx = valid_df.index[i-1]
            raw_segments.append((current_state, int(start_idx), int(end_idx)))
            start_idx = valid_df.index[i]
            current_state = valid_df['state'].iloc[i]
    raw_segments.append((current_state, int(start_idx), int(valid_df.index[-1])))

    # ============ 4. 合并短片段 + 震荡吞没 ============
    merged = []
    for state, s, e in raw_segments:
        length = e - s + 1
        if length <= min_seg_len and merged:
            # 短片段并入前一段，状态随前一段
            prev_state, prev_s, prev_e = merged[-1]
            merged[-1] = (prev_state, prev_s, e)
        else:
            merged.append((state, s, e))

    # 二次合并相邻同状态
    final = []
    for seg in merged:
        if not final:
            final.append(seg)
            continue
        last_state, last_s, last_e = final[-1]
        state, s, e = seg
        if state == last_state:
            final[-1] = (state, last_s, e)
        else:
            final.append(seg)

    # ============ 5. 输出 ============
    result = {'bull': [], 'bear': [], 'range': []}
    for state, s, e in final:
        result[state].append((s, e))

    if mode == 'last':
        return {k: (result[k][-1] if result[k] else None) for k in ['bull', 'bear', 'range']}
    return result