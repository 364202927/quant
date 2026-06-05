from typing import TypedDict

kPm = 'PortfolioMargin' #统一账号
kSpot, kSwap, kFuture, kDelivery = 'spot', 'swap', 'future', 'delivery'
kBuy, kSell, kFind = 'buy', 'sell', 'find'
kMarket, kLimit = 'MARKET', 'LIMIT'
kLong, kShort = 'LONG', 'SHORT'


# kEvt_Market 子消息 ID
eMarketId = {
    # 行情（public WS）
    # 'mKline':       1001,
    # 'mDepth':       1002,
    # 'mTrades':      1003,
    # # 用户数据（private WS）
    # 'mBalance':     1100,
    # 'mPosition':    1101,
    # 'mOrder':       1102,
    # # 策略 → OMS 信号
    # 'sOrder':       2001,
    # 'sCancel':      2002,
    # 'sForceClose':  2003,
    # 'omsOrder':     2100,  # 经 preTrade 拦截后转入 OMS
    # # 内部聚合通知
    # 'iHolding':     3001,
    # 'iCircuitTrip': 3002,
    # REST 初始化快照

    # 缓存
    'balance':      1000,
    'positions':    1001,

    #ws
    'wsBalance':    1100,   #ws个人数据更新
    'wsOrder':      1101,   #ws order更新

    #set
    'scKline':      1200,   #订阅k线数据         
    #get
    'gcKline':      1300,   #获取k线
}

# PriorityQueue 优先级（小值优先） oms
kPriority_ForceClose = 0
kPriority_Cancel     = 1
kPriority_Normal     = 5


# 导出市场相关类（必须放在常量之后避免循环导入）
from server.market.baseExchange import baseExchange
from server.market.marketMgr import marketMgr

__all__ = [
    'kPm', 'kSpot', 'kSwap', 'kFuture', 'kDelivery',
    'kBuy', 'kSell', 'kFind', 'kMarket', 'kLimit',
    'kLong', 'kShort',
    # market event ids
    'eMarketId',
    'kPriority_ForceClose', 'kPriority_Cancel', 'kPriority_Normal',
    # classes
    'baseExchange', 'marketMgr',
]
