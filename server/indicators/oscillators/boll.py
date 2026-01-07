from indicators.baseIndicators import *
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
    '布林线指标'

    # 默认指标
    _maDay = 30  # 均线：交易时间线，股票是20天，币是30天
    _stDev = 2  # 标准差：数字越大开口越阔，触发的信号越不频繁

    def init(self):
        self._pd.setHead(['candle_begin_time', "median",
                         "std", "upper", "lower", 'bbw', '%B'])

    def delimit(self, **kWargs):
        if kWargs.get('maDay'):
            self._maDay = kWargs['maDay']
        if kWargs.get('stdev'):
            self._stdev = kWargs['stdev']

    def calculate(self, pd):
        self._pd.format(pd, style="copy")
        self._bollTrack(pd)
        return self._pd

    # 计算均线和boll上下轨
    def _bollTrack(self, sor_pd):
        pd = self._pd.get()
        # 均线 = n天收盘价的 公式：a = 平均值(1+...)/n  b = sum((当前值-a)平方) c = 根号(b/(len -
        # 1))
        pd['median'] = sor_pd['close'].rolling(window=self._maDay).mean()
        # 上下轨 公式(当前值-均值)
        pd['std'] = sor_pd['close'].rolling(
            window=self._maDay).std(
            ddof=0)  # ddof代表标准差自由度
        pd['upper'] = pd['median'] + self._stDev * pd['std']
        pd['lower'] = pd['median'] - self._stDev * pd['std']
        # boll宽度
        pd['bbw'] = (pd['upper'] - pd['lower']) / pd['median']
        # %B
        pd['%B'] = (sor_pd['close'] - pd['lower']) / \
            (pd['upper'] - pd['lower'])
        # 布林带趋势
        pd['BBTrend'] = np.where(sor_pd['close'] > pd['upper'], 2,  # 强烈上升
                                 np.where(sor_pd['close'] > pd['median'], 1,  # 上升
                                          np.where(sor_pd['close'] > pd['lower'], -1,  # 下降
                                                   -2)))  # 强烈下降
