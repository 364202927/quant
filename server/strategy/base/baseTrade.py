"""交易基类 - 声明下单接口，由 realTrade 实现具体逻辑"""


class baseTrade:
    "交易基类"
    
    def __init__(self):
        super().__init__()

    def settingTrade(self, exName: str, defLv: int = 1) -> None:
        self._exName = exName
        self._defLv = defLv

    # ── 现货 ──
    def buy(self, symbol: str, totelPrice: float | str, orderBook: int = 0,
            price: float | None = None, inForce: str = 'GTC',
            exName: list[str] | None = None) -> None:
        raise NotImplementedError

    def sell(self, symbol: str, totelPrice: float | str = 'bet:100',
             orderBook: int = 0, price: float | None = None,
             inForce: str = 'GTC', exName: list[str] | None = None) -> None:
        raise NotImplementedError

    def cancel(self, symbol: str, orderID: str = '',
               exName: list[str] | None = None) -> None:
        raise NotImplementedError

    # ── 合约 ──
    def openLong(self, symbol: str, totelPrice: float | str,
                 orderBook: int = 0, price: float | None = None,
                 lv: int = 0, isMarket: bool = False,
                 inForce: str = 'GTC', exName: list[str] | None = None) -> None:
        raise NotImplementedError

    def openShort(self, symbol: str, totelPrice: float | str,
                  orderBook: int = 0, price: float | None = None,
                  lv: int = 0, isMarket: bool = False,
                  inForce: str = 'GTC', exName: list[str] | None = None) -> None:
        raise NotImplementedError

    def closePos(self, symbol: str, dir: str = 'all',
                 totelPrice: float | str = 'bet:100', orderBook: int = 0,
                 price: float | None = None, lv: int = 0,
                 isMarket: bool = False, inForce: str = 'GTC',
                 exName: list[str] | None = None) -> None:
        raise NotImplementedError

    # ── 下单（子类实现） ──
    def order(self, state: str, symbol: str, ex, lv: int,
              totelPrice: float, price: float | None,
              amount: float | None, isMarket: bool,
              inForce: str, posSide: str | None) -> None:
        raise NotImplementedError

    # ── 持仓查询 ──
    def checkPos(self, ex) -> list:
        """检查对应交易所的持仓，返回持仓列表"""
        if not ex:
            return []
        _, pos_orders = ex.findOrder(symbol='', isPos=True, isOpen=False)
        return pos_orders
