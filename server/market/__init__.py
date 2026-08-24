from typing import TypedDict

kPm = 'PortfolioMargin' #统一账号
kSpot, kSwap, kCancel,kClose = 'spot', 'swap', 'cancel', 'close'
kBuy, kSell, kFind = 'buy', 'sell', 'find'
kMarket, kLimit = 'MARKET', 'LIMIT'
kFuture, kDelivery = 'future', 'delivery' #todo:不要了
kLong, kShort = 'LONG', 'SHORT'

# ccxt 统一后的订单失败终态。交易所原始状态会被 ccxt 转换成这些值之一。
kOrderFailedStatuses: tuple[str, ...] = (
    'cancel', 'canceled', 'cancelled', 'rejected', 'expired', 'failed'
)


# kEvt_Market 子消息 ID
eMarketId = {
    # 缓存
    'balance':      1000,       # 初始化账号数据
    'positions':    1001,       # 初始化仓位数据
    'submit':       1002,       # 策略下单意图入队 (需关键字type列出类型:kSpot/kSwap/kCancel)
    'order':        1004,       # 下单已提交,记录待匹配
    'orderFailed':  1005,       # 下单失败,回滚待匹配记录
    'orderAccepted':1006,       # REST已返回交易所orderID,回填待匹配记录

    #ws
    'wsBalance':    1100,       #ws 个人数据更新
    'wsOrder':      1101,       #ws order更新

    #set
    'scKline':      1200,       #订阅k线数据         
    #get
    'gcKline':      1300,       #获取k线
    'gBalance':     1301,       #获得center balance数据
    'gPosit' :      1302,       #检测交易所是否存在持仓
    'gOpenOrders':  1303,       #获取本地待成交订单
    'uOpenOrder':   1304,       #更新本地待成交订单追踪信息
    'checkOrders':  1305,       #检查待成交订单
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
    'kOrderFailedStatuses',
    # market event ids
    'eMarketId',
    'kPriority_ForceClose', 'kPriority_Cancel', 'kPriority_Normal',
    # classes
    'baseExchange', 'marketMgr',
]
