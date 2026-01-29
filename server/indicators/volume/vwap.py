from server.indicators.baseIndicators import *

# VWAP是成交量加权平均价格指标
# 公式：VWAP = Σ(价格 × 成交量) / Σ(成交量)
# 应用：
# 1. 用于判断价格是否合理
# 2. 当价格>VWAP表示价格被高估
# 3. 当价格<VWAP表示价格被低估
# 4. 常用于日内交易和短期交易


class vwap(baseIndicators):
    """成交量加权平均价格 (Volume Weighted Average Price)

    公式: VWAP = 累积(典型价格 * 成交量) / 累积成交量
    典型价格 = (high + low + close) / 3

    参数:
    - period: 滚动窗口周期，0表示累积VWAP（默认20）

    应用:
    - 价格 > VWAP: 价格被高估
    - 价格 < VWAP: 价格被低估
    """

    def init(self) -> None:
        self._period = 20  # 滚动窗口周期，0表示累积VWAP
        self._pd.setHead(['candle_begin_time', 'vwap'])

    def delimit(self, **kwargs) -> None:
        self._period = kwargs.get('period', self._period)

    def calculate(self, pd: pdData) -> 'pdData':
        self._pd.format(pd, style="copy")
        self._computeVwap(pd)
        return self._pd

    def calculateTa(self, pd: pdData) -> 'pdData':
        return self.calculate(pd)

    def _computeVwap(self, sor_pd: pdData) -> None:
        pf = self._pd.get()
        typical_price = (sor_pd['high'] + sor_pd['low'] + sor_pd['close']) / 3
        price_vol = typical_price * sor_pd['vol']

        if self._period > 0:
            # 滚动VWAP
            cum_price_vol = price_vol.rolling(window=self._period).sum()
            cum_vol = sor_pd['vol'].rolling(window=self._period).sum()
        else:
            # 累积VWAP
            cum_price_vol = price_vol.cumsum()
            cum_vol = sor_pd['vol'].cumsum()

        pf['vwap'] = (cum_price_vol / cum_vol).round(2)
