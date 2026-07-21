from server.strategy.base.baseTrade import baseTrade
from server.utils import evtFire, kEvt_Market, spot
from server.market import eMarketId, kSpot, kSwap, kCancel, kBuy, kSell, kLong, kShort,kClose

# ##todo:任务亏损超过n,不让下单
# #todo:ismarket可以去掉,overbook少于0 = 市价开单

class realTrade(baseTrade):
    "订单->发送交易所"

    def __init__(self):
        super().__init__()

    # 所有订单共用的默认字段,子类/业务方法只需在此基础上覆盖差异字段
    def _order(self, **fields) -> dict:
        base = {
            'taskName': self.name(),
            'amount': None,
            'inForce': 'GTC',
        }
        return {**base, **fields}

    # 现货订单固定逻辑:type/symbol/lv/posSide/isMarket都是套路,调用方只传真正变化的值
    def _spotOrder(self, symbol: str, dir: str, totelPrice, orderBook: int, price, inForce: str) -> dict:
        return self._order(
            type=kSpot,
            symbol=spot(symbol),
            totelPrice=totelPrice,
            orderBook=orderBook,
            price=price,
            isMarket=price is None and orderBook < 0,
            inForce=inForce,
            lv=0,
            posSide=None,
            dir=dir,
        )

    # 合约订单固定逻辑:type/symbol/杠杆兜底都是套路,调用方只传方向、仓位方向等差异值
    def _swapOrder(self, symbol: str, dir: str, posSide: str, totelPrice, orderBook: int,
                   price, lv: int, isMarket: bool, inForce: str) -> dict:
        return self._order(
            type=kSwap,
            symbol=symbol,
            totelPrice=totelPrice,
            orderBook=orderBook,
            price=price,
            isMarket=isMarket,
            inForce=inForce,
            lv=self._defLv if lv == 0 else lv,
            posSide=posSide,
            dir=dir,
        )

    # 遍历交易所+发事件,统一在这里给每份data补上对应的exName
    def _dispatch(self, evtId, exName, data: dict) -> None:
        targets = exName if exName else [self._exName]
        for name in targets: #多交易所
            evtFire(kEvt_Market, evtId, {**data, 'exName': name})

    # ── 现货 ──
    def buy(self, symbol: str, totelPrice: float | str, orderBook: int = 0,price: float | None = None, inForce: str = 'GTC', exName: list[str] | None = None) -> None:
        data = self._spotOrder(symbol, kBuy, totelPrice, orderBook, price, inForce)
        self._dispatch(eMarketId['preTrade'], exName, data)

    def sell(self, symbol: str, totelPrice: float | str = 'bet:100',orderBook: int = 0, price: float | None = None,inForce: str = 'GTC', exName: list[str] | None = None) -> None:
        data = self._spotOrder(symbol, kSell, totelPrice, orderBook, price, inForce)
        self._dispatch(eMarketId['preTrade'], exName, data)

    def cencel(self, symbol: str, orderID: str = '',exName: list[str] | None = None) -> None:
        data = {
            'type': kCancel,
            'taskName': self.name(),
            'symbol': symbol,
            'orderID': orderID,
        }
        self._dispatch(eMarketId['oms'], exName, data)

    # ── 合约 ──
    def openLong(self, symbol: str, totelPrice: float | str, orderBook: int = 0, price: float | None = None,lv: int = 0, isMarket: bool = False, inForce: str = 'GTC', exName: list[str] | None = None) -> None:
        data = self._swapOrder(symbol, kBuy, kLong, totelPrice, orderBook, price, lv, isMarket, inForce)
        self._dispatch(eMarketId['preTrade'], exName, data)

    def openShort(self, symbol: str, totelPrice: float | str,orderBook: int = 0, price: float | None = None, lv: int = 0, isMarket: bool = False,inForce: str = 'GTC', exName: list[str] | None = None) -> None:
        data = self._swapOrder(symbol, kSell, kShort, totelPrice, orderBook, price, lv, isMarket, inForce)
        self._dispatch(eMarketId['preTrade'], exName, data)

    def closePos(self, symbol: str, dir: str, totelPrice: float | str = 'bet:100', orderBook: int = 0,price: float | None = None, lv: int = 0, isMarket: bool = False, inForce: str = 'GTC', exName: list[str] | None = None) -> None:
        data = self._swapOrder(symbol, kClose, dir, totelPrice, orderBook, price, lv, isMarket, inForce)
        self._dispatch(eMarketId['preTrade'], exName, data)