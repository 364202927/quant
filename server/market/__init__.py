from typing import TypedDict

# 交易/账户常量（原 consts.py）
kPm = 'PortfolioMargin'
kSpot, kSwap, kFuture, kDelivery = 'spot', 'swap', 'future', 'delivery'
kBuy, kSell, kFind = 'buy', 'sell', 'find'
kMarket, kLimit = 'MARKET', 'LIMIT'
kLong, kShort = 'LONG', 'SHORT'


class OrderResult(TypedDict, total=False):
    orderId: str
    symbol: str
    status: str         # 'open' | 'closed' | 'cancel'
    side: str           # 'buy' | 'sell'
    positionSide: str   # 'LONG' | 'SHORT' | None
    origQty: float
    avgPrice: float
    cumQuote: float
    fee: float
    time: int
    updateTime: int


# kEvt_Market 子消息 ID
eMarketId = {
    # 行情（public WS）
    'mKline':       1001,
    'mDepth':       1002,
    'mTrades':      1003,
    # 用户数据（private WS）
    'mBalance':     1100,
    'mPosition':    1101,
    'mOrder':       1102,
    # 策略 → OMS 信号
    'sOrder':       2001,
    'sCancel':      2002,
    'sForceClose':  2003,
    'omsOrder':     2100,  # 经 preTrade 拦截后转入 OMS
    # 内部聚合通知
    'iHolding':     3001,
    'iCircuitTrip': 3002,
}

# PriorityQueue 优先级（小值优先）
kPriority_ForceClose = 0
kPriority_Cancel     = 1
kPriority_Normal     = 5


# 导出市场相关类（必须放在常量之后避免循环导入）
from server.market.baseExchange import baseExchange
from server.market.marketMgr import marketMgr

__all__ = [
    # consts
    'kPm', 'kSpot', 'kSwap', 'kFuture', 'kDelivery',
    'kBuy', 'kSell', 'kFind', 'kMarket', 'kLimit',
    'kLong', 'kShort', 'OrderResult',
    # market event ids
    'eMarketId',
    'kPriority_ForceClose', 'kPriority_Cancel', 'kPriority_Normal',
    # classes
    'baseExchange', 'marketMgr',
]
