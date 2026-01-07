from indicators.baseIndicators import *
# K：反映短期市场波动，是最敏感的一条线。 D：反映中期市场波动，较为平滑，是K线的移动平均线。J：反映K线和D线的离差，波动最为剧烈。
# 超买超卖判断：K值在80以上为超买区，20以下为超卖区。
# 金叉和死叉：K线向上穿过D线时，形成金叉，通常是买入信号。K线向下穿过D线时，形成死叉，通常是卖出信号。
# KDJ指标比RSI更为敏感，适合短期交易


class kdj(baseIndicators):
    '随机指标'

    _period = 20        # rsv的周期
    _signal = 3         # 指数平滑，值越小越敏感越大越滞后
    # 1.period（KDJ的计算周期）：
    # 短期交易（如日内交易）：可以选择较短的周期，例如 9、14 或 21。这样可以更快速地响应市场变化。
    # 中长期交易：可以选择较长的周期，例如 50 或 100。这样可以平滑一些短期的波动，更关注大的趋势。
    # 2.signal（平滑系数）：
    # 较小的 signal（例如 1 或 2）：更适用于短期交易，这样KDJ指标会对价格的变化更敏感，但可能会产生更多噪音。
    # 较大的 signal（例如 3 或 5）：更适用于中长期交易，指标变化较平滑，但可能会滞后于市场价格变化。

    def init(self):
        self._pd.setHead(['candle_begin_time', 'k', 'd', 'j'])

    def delimit(self, **kWargs):
        if kWargs.get('period'):
            self._period = kWargs['period']
        if kWargs.get('signal'):
            self._signal = kWargs['signal']

    def calculate(self, pd):
        self._pd.format(pd, style="copy")
        self._kdjTrack(pd)
        # self._taKdj(pd)
        return self._pd

    def _kdjTrack(self, sor_pd):
        pf = self._pd.get()
        low_min = sor_pd['low'].rolling(
            window=self._period, min_periods=1).min()
        high_max = sor_pd['high'].rolling(
            window=self._period, min_periods=1).max()
        rev = (sor_pd['close'] - low_min) / \
            (high_max - low_min) * 100  # 未成熟随机数
        pf['k'] = rev.ewm(com=self._signal, adjust=False).mean()
        pf['k'] = pf['k'].round(1)
        pf['d'] = pf['k'].ewm(com=self._signal, adjust=False).mean()
        pf['d'] = pf['d'].round(1)
        pf['j'] = 3 * pf['k'] - 2 * pf['d']
        pf['j'] = pf['j'].round(1)

    def _taKdj(self, sor_pd):
        pf = self._pd.get()
        rsv = ta.momentum.stoch(
            sor_pd['high'],
            sor_pd['low'],
            sor_pd['close'],
            window=self._period)
        pf['k'] = rsv.ewm(com=self._signal, adjust=False).mean()
        pf['k'] = pf['k'].round(1)
        pf['d'] = pf['k'].ewm(com=self._signal, adjust=False).mean()
        pf['d'] = pf['d'].round(1)
        pf['j'] = 3 * pf['k'] - 2 * pf['d']
        pf['j'] = pf['j'].round(1)
