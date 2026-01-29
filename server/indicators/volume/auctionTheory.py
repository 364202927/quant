from server.indicators.baseIndicators import *

# 正态分布vp
# atr波动率
# 拍卖理论用于分析市场中的买卖力量对比
# 1. 上升拍卖：价格上升且成交量增加
# 2. 下降拍卖：价格下降且成交量增加
# 3. 接纳(Acceptance)：价格离开开盘价但成交量不增加
# 4. 拒绝(Rejection)：价格返回到开盘价且成交量不增加


class auctionTheory(baseIndicators):
    """拍卖理论 (Auction Theory)

    分析市场中的买卖力量对比:
    - market_strength: 市场强度 = volume * price_change / (high_low_range + 1)
    - buyer_pressure: 买方压力 = (close - open) * volume 的滚动累积
    - seller_pressure: 卖方压力 = (open - close) * volume 的滚动累积
    """

    def info(self) -> str:
        return "拍卖理论"

    def init(self) -> None:
        self._period = 20
        self._pd.setHead(['candle_begin_time', 'market_strength', 'buyer_pressure', 'seller_pressure'])

    def delimit(self, **kwargs) -> None:
        self._period = kwargs.get('period', self._period)

    def calculate(self, pd: pdData) -> 'pdData':
        self._pd.format(pd, style="copy")
        self._computeAuction(pd)
        return self._pd

    def calculateTa(self, pd: pdData) -> 'pdData':
        return self.calculate(pd)

    def _computeAuction(self, sor_pd: pdData) -> None:
        """计算拍卖理论指标 (自写和talib共用)"""
        pf = self._pd.get()
        price_change = sor_pd['close'] - sor_pd['open']
        high_low_range = sor_pd['high'] - sor_pd['low']
        volume = sor_pd['vol']
        window = self._period

        # 市场强度
        pf['market_strength'] = (volume * price_change / (high_low_range + 1)).rolling(window=window).mean().round(2)
        # 买方压力
        pf['buyer_pressure'] = (price_change * volume).rolling(window=window).sum().round(2)
        # 卖方压力 = -买方压力
        pf['seller_pressure'] = (-price_change * volume).rolling(window=window).sum().round(2)
