import math,time,random,ta
import pandas as pd
from decimal import Decimal, ROUND_UP
# from server.utils.common import switchFn
# from server.market.consts import kLong,kShort,kBuy,kSell
# from hmmlearn import hmm

# import numpy as np

# 是否落在范围
def inRange(range, num):
    min = 0 if range[0] is None else float(range[0])
    max = math.inf if range[1] is None else float(range[1])
    return min <= float(num) <= max

# def percentage(total, strPercentage):
#     if strPercentage.endswith('%'):
#             percentage = float(strPercentage[:-1])
#             # result = (percentage / 100) * value
#             return (percentage * 0.01) * strPercentage
#     return total

# 根据当前时间返回id
def time2ID():
    timestamp = int(time.time() * 1000000)
    rand_num = random.randint(0, 999999)
    return f"{timestamp}{rand_num:06d}"# 使用格式化字符串强制随机数占满 6 位

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


# ======== 交易成本与账户口径: backTest(指标回测) 与 testTrade(模拟交易) 共用一份 ========
kFeeRate = 0.0005               # 单边吃单手续费率
kSlip = (0.0001, 0.0005, 42)    # 默认滑点区间 [最小, 最大, 随机种子]
kFundingFreq = '8h'             # 资金费结算周期(UTC 00/08/16)
kMarginRatio = 0.95             # 起始权益占本金比例,剩余 5% 作为缓冲
kLiqRatio = 0.1                 # 净值跌破 初始权益×该比例 → 强平(爆仓)

# 手续费: qty 成交数量, price 成交价
def feeCost(qty, price, rate=kFeeRate):
    return qty * price * rate

# 按滑点偏移成交价: side=±1,滑点始终取不利方向
def slipPrice(price, side, slip):
    return price * (1 + side * slip)

# 滑点区间 [最小, 最大, 种子]: 缺省或 None 的项取 kSlip
def slipRange(slip=None):
    given = list(slip or ())[:3]
    return [d if v is None else v for d, v in zip(kSlip, given + [None] * (3 - len(given)))]

# 资金费结算时刻: 缺失结算 K 线时 df.loc 会直接 KeyError(数据必须含 00/08/16 UTC)
def fundingTimes(index):
    return pd.date_range(index[0].ceil(kFundingFreq), index[-1], freq=kFundingFreq)

# 结算表 {结算时刻: (结算价, 费率)}; 无 funding_bps 列返回空表
def fundingTable(df):
    if "funding_bps" not in df.columns:
        return {}
    rows = df.loc[fundingTimes(df.index)]
    return dict(zip(rows.index, zip(rows["open"], rows["funding_bps"] / 1e4)))

# 资金费: 多头付正费率,空头收正费率
def fundingPay(qty, price, rate, side):
    return qty * price * rate * side 

# 通用下单门禁: 未爆仓 + 在允许时段 + 有可用保证金
# clock: UTC 时钟 "HH:MM:SS"; avail: 可用保证金(净值-已占用); session: (起, 止) 或 None 不限时段
def canOrder(clock, avail, session=None, blown=False):
    if blown or avail <= 0:
        return False
    return session is None or session[0] <= clock <= session[1]