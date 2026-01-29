from server.indicators.baseIndicators import *
import talib

# 使用方法
# 1.布林带更多是用来预测趋势，不要用来抓反转
# 2.开口情况需注意，开始有人来参与，股价会有波动 (开口是上轨-下轨 >10%,也能使用%B或bbw判断)
# 适用震荡市场，因为标准差能够快速捕捉到价格的极端变化。
# 适合在震荡市场中使用，以识别价格的极端点并寻找反转机会。

# bbw布林带宽度
# Bollinger Bands Width = (Upper Band - Lower Band) / Middle Band
# 看涨BBW收缩，BBW下跌。价格突破上限带，开始新的上升趋势。波动性也增加。
# 看跌BBW收缩，BBW下跌。价格跌破下限带，开始新的下降趋势。波动性也增加。

# 布林帶%B
# %B = (Current Price - Lower Band) / (Upper Band - Lower Band)
# %B 大于 1 = 价格在上限带之上
# %B 等于 1 = 价格落在上限带
# %B 大于 .50 = 价格在中线之上
# %B 小于.50 = 价格在中线之下
# %B 等于 0 = 价格落在下限带
# %B 小于 0 = 价格在下限带之下
# ％B高于.80 =价格已接近上限带
# ％B低于.20 =价格已接近下限带


class boll(baseIndicators):
    """布林线指标 (Bollinger Bands)

    参数:
    - maDay: 均线周期（默认30，股票用20，币用30）
    - stDev: 标准差倍数（默认2，越大开口越阔）
    """

    def init(self) -> None:
        self._maDay = 30  # 均线：交易时间线，股票是20天，币是30天
        self._stDev = 2   # 标准差：数字越大开口越阔，触发的信号越不频繁
        self._pd.setHead(['candle_begin_time', "median",
                         "std", "upper", "lower", 'bbw', '%B'])

    def delimit(self, **kwargs) -> None:
        self._maDay = kwargs.get('maDay', self._maDay)
        self._stDev = kwargs.get('stDev', self._stDev)

    def calculate(self, pd: pdData) -> 'pdData':
        self._pd.format(pd, style="copy")
        self._bollTrack(pd)
        return self._pd

    def calculateTa(self, pd: pdData) -> 'pdData':
        self._pd.format(pd, style="copy")
        self._taBoll(pd)
        return self._pd

    def _bollTrack(self, sor_pd: pdData) -> None:
        pf = self._pd.get()
        close = sor_pd['close']
        # 均线
        pf['median'] = close.rolling(window=self._maDay).mean()
        # 标准差
        pf['std'] = close.rolling(window=self._maDay).std(ddof=0)
        # 上下轨
        pf['upper'] = pf['median'] + self._stDev * pf['std']
        pf['lower'] = pf['median'] - self._stDev * pf['std']
        # boll宽度
        pf['bbw'] = (pf['upper'] - pf['lower']) / pf['median']
        # %B
        pf['%B'] = (close - pf['lower']) / (pf['upper'] - pf['lower'])
        # 布林带趋势
        pf['BBTrend'] = np.where(close > pf['upper'], 2,           # 强烈上升
                                 np.where(close > pf['median'], 1,  # 上升
                                          np.where(close > pf['lower'], -1,  # 下降
                                                   -2)))            # 强烈下降

    def _taBoll(self, sor_pd: pdData) -> None:
        pf = self._pd.get()
        close = sor_pd['close'].values
        upper, median, lower = talib.BBANDS(close, timeperiod=self._maDay, nbdevup=self._stDev, nbdevdn=self._stDev, matype=0)
        pf['median'] = median
        pf['std'] = (upper - median) / self._stDev
        pf['upper'] = upper
        pf['lower'] = lower
        # boll宽度
        pf['bbw'] = (upper - lower) / median
        # %B
        pf['%B'] = (sor_pd['close'].values - lower) / (upper - lower)
        # 布林带趋势
        pf['BBTrend'] = np.where(sor_pd['close'].values > upper, 2,
                                 np.where(sor_pd['close'].values > median, 1,
                                          np.where(sor_pd['close'].values > lower, -1, -2)))
