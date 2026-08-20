from server.indicators.baseIndicators import *
from server.utils import utc_now

# VWAP是成交量加权平均价格指标
# 公式：VWAP = Σ(价格 × 成交量) / Σ(成交量)
# 应用：
# 1. 用于判断价格是否合理
# 2. 当价格>VWAP表示价格被高估
# 3. 当价格<VWAP表示价格被低估
# 4. 常用于日内交易和短期交易

class vwap(baseIndicators):
    def init(self) -> None:
        self._period = 0  # 滚动窗口周期，0表示累积VWAP
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
        pf = self._pd.raw()
        typical_price = (sor_pd['high'] + sor_pd['low'] + sor_pd['close']) / 3
        price_vol = typical_price * sor_pd['vol']
        # Extract date from candle_begin_time for daily grouping
        local_time = sor_pd['candle_begin_time'] + pd.Timedelta(hours=utc_now())
        group_col = local_time.dt.date
        if self._period > 0:# Rolling VWAP (reset per day)
            cum_price_vol = price_vol.groupby(group_col).rolling(window=self._period, min_periods=1).sum().reset_index(level=0, drop=True)
            cum_vol = sor_pd['vol'].groupby(group_col).rolling(window=self._period, min_periods=1).sum().reset_index(level=0, drop=True)
        else:# Cumulative intraday VWAP (standard usage)
            cum_price_vol = price_vol.groupby(group_col).cumsum()
            cum_vol = sor_pd['vol'].groupby(group_col).cumsum()

        pf['vwap'] = (cum_price_vol / cum_vol.replace(0, np.nan)).round(2)
