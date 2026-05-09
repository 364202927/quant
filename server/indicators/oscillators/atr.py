from server.indicators.baseIndicators import *

# 震荡指标
# 突破时可作为参考，如果波动大则代表此突破有可能为真
# 可做止损止盈用途
# 高波动大止损点
# 低波动小止损点


# 当价格下跌跌破关键价位后，ATR同时也正在增加这意味下跌波动越来越大，卖方的力量也逐渐增加所以大概率这一个跌破是确实的并有效


class atr(baseIndicators):
    """平均真实波动幅度 (Average True Range)

    用于衡量市场波动性，可作为止损止盈参考：
    - 高波动 -> 大止损点
    - 低波动 -> 小止损点
    - 价格突破关键位时ATR增加，表示突破可能有效
    """

    def init(self) -> None:
        self._period = 14

    def delimit(self, **kwargs) -> None:
        self._period = kwargs.get('period', self._period)

    def calculate(self, pd: pdData) -> pdData:
        return pdData(data=self._atrTrack(pd), style='copy')

    def calculateTa(self, pd: pdData) -> pdData:
        return pdData(data=self._taAtr(pd), style='copy')

    def _atrTrack(self, sor_pd: pdData) -> any:
        pf = sor_pd.copy()
        sor_pd = sor_pd.get()
        prev_close = sor_pd['close'].shift()
        # 计算真实波幅(TR): max(high-low, |high-prev_close|, |low-prev_close|)
        tr = np.maximum(
            sor_pd['high'] - sor_pd['low'],
            np.maximum(np.abs(sor_pd['high'] - prev_close), np.abs(sor_pd['low'] - prev_close))
        )
        pf['tr'] = tr
        alpha = 1.0 / self._period
        pf['atr'] = tr.ewm(alpha=alpha, adjust=False).mean().round(2)
        return pf

    def _taAtr(self, sor_pd: pdData) -> any:
        pf = sor_pd.copy()
        sor_pd = sor_pd.get()
        high, low, close = sor_pd['high'].values, sor_pd['low'].values, sor_pd['close'].values
        pf['tr'] = talib.TRANGE(high, low, close)
        pf['atr'] = talib.ATR(high, low, close, timeperiod=self._period)
        return pf
