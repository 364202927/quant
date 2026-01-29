from server.indicators.baseIndicators import *
import talib

# https://www.youtube.com/watch?v=RMyTf1VYvMw
# https://www.youtube.com/watch?v=_BL8s4MQGMg

# 量价关系
# https://www.youtube.com/watch?v=HnXObqWHjvU


# rsi策略
# rsi70是超买，30是超卖
# 抄底要在低于向上突破30时进行买入
# 卖出要在向下突破70是卖出

# 判断止跌要在关键k最高最低点进行记录，如果突破则止跌了


# stoch rsi
# 日k，长线使用rsi，短线使用stoch rsi


class rsi(baseIndicators):
    """RSI相对强度指数 (Relative Strength Index)

    策略说明:
    - RSI > 70: 超买区域，向下突破70时卖出
    - RSI < 30: 超卖区域，向上突破30时买入
    - 日K长线用RSI，短线用Stoch RSI
    """

    def init(self) -> None:
        self._period = 14
        self._pd.setHead(['candle_begin_time', 'rsi'])

    def delimit(self, **kwargs) -> None:
        self._period = kwargs.get('period', self._period)

    def calculate(self, pd: pdData) -> 'pdData':
        self._pd.format(pd, style="copy")
        self._rsiTrack(pd)
        return self._pd

    def calculateTa(self, pd: pdData) -> 'pdData':
        self._pd.format(pd, style="copy")
        self._taRsi(pd)
        return self._pd

    def _rsiTrack(self, sor_pd: pdData) -> None:
        """自写算法计算RSI"""
        pf = self._pd.get()
        delta = sor_pd['close'].diff()
        # 向量化计算收益和损失
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        # EMA平滑
        avg_gain = gain.ewm(span=self._period, adjust=False).mean()
        avg_loss = loss.ewm(span=self._period, adjust=False).mean()
        # RSI = 100 - 100/(1 + RS), RS = avg_gain/avg_loss
        pf['rsi'] = (100 - (100 / (1 + avg_gain / avg_loss))).round(2)

    def _taRsi(self, sor_pd: pdData) -> None:
        """使用talib计算RSI"""
        pf = self._pd.get()
        pf['rsi'] = talib.RSI(sor_pd['close'].values, timeperiod=self._period).round(2)
