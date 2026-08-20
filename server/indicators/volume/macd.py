from server.indicators.baseIndicators import *
import talib

# https://www.youtube.com/watch?v=kBnAQwLtAKc

# MACD是趋势跟踪动量指标
# DIF（MACD线）: 快速EMA(12) - 慢速EMA(26)
# DEA（信号线）: DIF的9日EMA
# MACD直方图: 2 * (DIF - DEA)
# 应用：
# 1. 当DIF向上穿过DEA时产生买入信号
# 2. 当DIF向下穿过DEA时产生卖出信号
# 3. 直方图为正且扩大表示上升趋势加强
# 4. 直方图为负且扩大表示下降趋势加强


class macd(baseIndicators):
    """MACD移动平均收敛发散 (Moving Average Convergence Divergence)

    组成:
    - DIF (MACD线): 快速EMA - 慢速EMA
    - DEA (信号线): DIF的EMA
    - MACD直方图: 2 * (DIF - DEA)

    信号:
    - DIF向上穿过DEA -> 买入信号
    - DIF向下穿过DEA -> 卖出信号
    - 直方图扩大表示趋势加强
    """

    def init(self) -> None:
        self._fast = 12    # 快速EMA周期
        self._slow = 26    # 慢速EMA周期
        self._signal = 9   # 信号线EMA周期

    def delimit(self, **kwargs) -> None:
        self._fast = kwargs.get('fast', self._fast)
        self._slow = kwargs.get('slow', self._slow)
        self._signal = kwargs.get('signal', self._signal)

    def calculate(self, pd: pdData) -> pdData:
        return pdData(data=self._macdTrack(pd), style='copy')

    def calculateTa(self, pd: pdData) -> pdData:
        return pdData(data=self._taMacd(pd), style='copy')

    def _macdTrack(self, sor_pd: pdData) -> any:
        pf = sor_pd.copy()
        sor_pd = sor_pd.raw()
        close = sor_pd['close']
        # DIF = 快EMA - 慢EMA
        dif = close.ewm(span=self._fast, adjust=False).mean() - close.ewm(span=self._slow, adjust=False).mean()
        dea = dif.ewm(span=self._signal, adjust=False).mean()
        pf['dif'] = dif.round(2)
        pf['dea'] = dea.round(2)
        pf['macd'] = (2 * (dif - dea)).round(2)
        return pf

    def _taMacd(self, sor_pd: pdData) -> any:
        pf = sor_pd.copy()
        sor_pd = sor_pd.raw()
        dif, dea, hist = talib.MACD(sor_pd['close'].values, fastperiod=self._fast, slowperiod=self._slow, signalperiod=self._signal)
        pf['dif'] = pd.Series(dif).round(2).values
        pf['dea'] = pd.Series(dea).round(2).values
        # talib返回的histogram是(DIF-DEA)，乘以2得到标准MACD
        pf['macd'] = pd.Series(hist * 2).round(2).values
        return pf
