"""交易基类 - 声明下单接口，由 realTrade(实盘) / testTrade(回测) 实现，策略代码两端通用"""


class baseTrade:
    """交易基类

    totelPrice: 数字=名义金额(USDT); 'bet:N'=可用余额的 N%
    orderBook < 0 表示市价单, 其余值按盘口/限价逻辑下单
    """

    _exName = ''    # 默认交易所, settingTrade 设置
    _defLv = 1      # 默认杠杆, 下单 lv=0 时使用

    def __init__(self):
        super().__init__()

    def settingTrade(self, exName: str, defLv: int = 1) -> None:
        """设置默认交易所和默认杠杆"""
        self._exName = exName
        self._defLv = defLv

    # ── 现货 ──
    def buy(self, symbol: str, totelPrice: float | str, orderBook: int = 0,
            price: float | None = None, inForce: str = 'GTC',
            exName: list[str] | None = None) -> None:
        """现货买入, totelPrice 为买入金额"""
        raise NotImplementedError

    def sell(self, symbol: str, totelPrice: float | str = 'bet:100',
             orderBook: int = 0, price: float | None = None,
             inForce: str = 'GTC', exName: list[str] | None = None) -> None:
        """现货卖出, 默认全部卖出"""
        raise NotImplementedError

    def cencel(self, symbol: str, orderID: str = '',
               exName: list[str] | None = None) -> None:
        """取消挂单"""
        raise NotImplementedError

    # ── 合约 ──
    def openLong(self, symbol: str, totelPrice: float | str,
                 orderBook: int = 0, price: float | None = None,
                 lv: int = 0,
                 inForce: str = 'GTC', exName: list[str] | None = None) -> None:
        """合约开多, totelPrice 为名义金额, 保证金=金额/lv"""
        raise NotImplementedError

    def openShort(self, symbol: str, totelPrice: float | str,
                  orderBook: int = 0, price: float | None = None,
                  lv: int = 0,
                  inForce: str = 'GTC', exName: list[str] | None = None) -> None:
        """合约开空, totelPrice 为名义金额, 保证金=金额/lv"""
        raise NotImplementedError

    def closePos(self, symbol: str, dir: str,
                 totelPrice: float | str = 'bet:100', orderBook: int = 0,
                 price: float | None = None, lv: int = 0,
                 inForce: str = 'GTC',
                 exName: list[str] | None = None) -> None:
        """合约平仓, dir=kLong/kShort/'all', 默认平全部持仓"""
        raise NotImplementedError
