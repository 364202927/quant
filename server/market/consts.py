from typing import TypedDict

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
