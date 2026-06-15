from typing import TypedDict

kPm = 'PortfolioMargin' #统一账号
kSpot, kSwap, kCancel,kClose = 'spot', 'swap', 'cancel', 'close'
kBuy, kSell, kFind = 'buy', 'sell', 'find'
kMarket, kLimit = 'MARKET', 'LIMIT'
kFuture, kDelivery = 'future', 'delivery' #todo:不要了
kLong, kShort = 'LONG', 'SHORT'


# kEvt_Market 子消息 ID
eMarketId = {
    # 缓存
    'balance':      1000,       # 初始化账号数据
    'positions':    1001,       # 初始化仓位数据
    'preTrade':     1002,       # 事前风险
    'oms':          1003,       # 下单数据 (需关键字type列出类型:kSpot/kSwap/kCancel)
    'order':        1004,       # 下单

    #ws
    'wsBalance':    1100,       #ws 个人数据更新
    'wsOrder':      1101,       #ws order更新

    #set
    'scKline':      1200,       #订阅k线数据         
    #get
    'gcKline':      1300,       #获取k线
    'gBalance':     1301,       #获得center balance数据
    'gPosit' :      1302,       #检测交易所是否存在持仓
}

# oms下单优先度
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
