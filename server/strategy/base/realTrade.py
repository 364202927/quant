from server.strategy.base.baseTrade import baseTrade
from server.utils import evtFire, kEvt_Market, spot
from server.market import eMarketId, kSpot, kSwap, kCancel, kBuy, kSell, kLong, kShort,kClose

#todo:cancel/sell/平仓 消息直接发到oms,不用走检测
#

class realTrade(baseTrade):
    "订单->发送交易所"

    def __init__(self):
        super().__init__()

    # ── 现货 ──
    def buy(self, symbol: str, totelPrice: float | str, orderBook: int = 0,price: float | None = None, inForce: str = 'GTC', exName: list[str] | None = None) -> None:
        targets = exName if exName else [self._exName]
        for name in targets: #多交易所
            data = {
                'type': kSpot,
                'taskName': self.name(),
                'symbol': spot(symbol),
                'totelPrice': totelPrice,
                'orderBook': orderBook,
                'price': price,
                'amount': None,
                'isMarket': price is None and orderBook < 0,
                'inForce': inForce,
                'lv': 0,
                'posSide': None,
                'dir': kBuy,
                'exName': name,
            }
            evtFire(kEvt_Market, eMarketId['preTrade'], data)

    def sell(self, symbol: str, totelPrice: float | str = 'bet:100',orderBook: int = 0, price: float | None = None,inForce: str = 'GTC', exName: list[str] | None = None) -> None:
        targets = exName if exName else [self._exName]
        for name in targets:
            data = {
                'type': kSpot,
                'taskName': self.name(),
                'symbol': spot(symbol),
                'totelPrice': totelPrice,
                'orderBook': orderBook,
                'price': price,
                'amount': None,
                'isMarket': price is None and orderBook < 0,
                'inForce': inForce,
                'lv': 0,
                'posSide': None,
                'dir': kSell,
                'exName': name,
            }
            evtFire(kEvt_Market, eMarketId['oms'], data)

    def cancel(self, symbol: str, orderID: str = '',exName: list[str] | None = None) -> None:
        targets = exName if exName else [self._exName]
        for name in targets:
            data = {
                'type': kCancel,
                'taskName': self.name(),
                'symbol': spot(symbol),
                'orderID': orderID,
                'exName': name,
            }
            # evtFire(kEvt_Market, eMarketId['preTrade'], data)

    # ── 合约 ──
    def openLong(self, symbol: str, totelPrice: float | str, orderBook: int = 0, price: float | None = None,lv: int = 0, isMarket: bool = False, inForce: str = 'GTC', exName: list[str] | None = None) -> None:
        lv = self._defLv if lv == 0 else lv
        targets = exName if exName else [self._exName]
        for name in targets:
            data = {
                'type': kSwap,
                'taskName': self.name(),
                'symbol': symbol,
                'totelPrice': totelPrice,
                'orderBook': orderBook,
                'price': price,
                'amount': None,
                'isMarket': isMarket,
                'inForce': inForce,
                'lv': lv,
                'posSide': kLong,
                'dir': kBuy,
                'exName': name,
            }
            evtFire(kEvt_Market, eMarketId['preTrade'], data)

    def openShort(self, symbol: str, totelPrice: float | str,orderBook: int = 0, price: float | None = None, lv: int = 0, isMarket: bool = False,inForce: str = 'GTC', exName: list[str] | None = None) -> None:
        lv = self._defLv if lv == 0 else lv
        targets = exName if exName else [self._exName]
        for name in targets:
            data = {
                'type': kSwap,
                'taskName': self.name(),
                'symbol': symbol,
                'totelPrice': totelPrice,
                'orderBook': orderBook,
                'price': price,
                'amount': None,
                'isMarket': isMarket,
                'inForce': inForce,
                'lv': lv,
                'posSide': kShort,
                'dir': kSell,
                'exName': name,
            }
            evtFire(kEvt_Market, eMarketId['preTrade'], data)

    def closePos(self, symbol: str, dir: str = 'all', totelPrice: float | str = 'bet:100', orderBook: int = 0,price: float | None = None, lv: int = 0, isMarket: bool = False, inForce: str = 'GTC', exName: list[str] | None = None) -> None:
        lv = self._defLv if lv == 0 else lv
        targets = exName if exName else [self._exName]
        for name in targets:
            data = {
                'type': kSwap,
                'taskName': self.name(),
                'symbol': symbol,
                'totelPrice': totelPrice,
                'orderBook': orderBook,
                'price': price,
                'amount': None,
                'isMarket': isMarket,
                'inForce': inForce,
                'lv': lv,
                'posSide': dir,
                'dir': kClose,
                'exName': name,
            }
            evtFire(kEvt_Market, eMarketId['preTrade'], data)
