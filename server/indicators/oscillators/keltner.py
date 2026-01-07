from indicators.baseIndicators import *
# 与boll类似，但会更敏感
# 适用于趋势跟踪，因为EMA和ATR能够更好地反映当前的市场趋势和波动性。
# 适合在趋势市场中使用，以识别价格回调或突破的机会。


class keltner(baseIndicators):
    '移动平均'

    _maDay = 20  # 均线：交易时间线，股票是20天，币是30天
    _atrult = 2  # atr,决定上下轨的宽度
    # 1.	self._maDay
    # 值越少对市场的波动越敏感，越大越容易过滤市场的杂音适用长周期
    # 2.	self._atrult
    # 值越少越贴近价格更容易识别突破和假突破，越大上下相距越宽更实用波动较大的长周期

    def init(self):
        self._pd.setHead(['candle_begin_time', 'ema',
                         'upper_band', 'lower_band', 'squeeze'])

    def delimit(self, **kWargs):
        if kWargs.get('maDay'):
            self._maDay = kWargs['maDay']
        if kWargs.get('atrult'):
            self._atrult = kWargs['atrult']

    def calculate(self, pd):
        self._pd.format(pd, style="copy")
        self._keltnerTrack(pd)
        # self._taTrack(pd)
        return self._pd

    def _keltnerTrack(self, sor_pd):
        pf = self._pd.get()
        pf['ema'] = sor_pd['close'].ewm(span=self._maDay, adjust=False).mean()
        high_low = sor_pd['high'] - sor_pd['low']
        high_close = np.abs(sor_pd['high'] - sor_pd['close'].shift())
        low_close = np.abs(sor_pd['low'] - sor_pd['close'].shift())
        tr = pd.DataFrame({'high_low': high_low,
                           'high_close': high_close,
                           'low_close': low_close}).max(axis=1)
        atr = tr.rolling(window=self._maDay).mean()
        pf['upper_band'] = pf['ema'] + (self._atrult * atr)
        pf['lower_band'] = pf['ema'] - (self._atrult * atr)

    def _taTrack(self, sor_pd):
        pf = self._pd.get()
        pf['ema'] = ta.trend.ema_indicator(sor_pd['close'], window=self._maDay)
        pf['atr'] = ta.volatility.average_true_range(
            sor_pd['high'], sor_pd['low'], sor_pd['close'], window=self._maDay)
        pf['upper_band'] = pf['ema'] + self._atrult * pf['atr']
        pf['lower_band'] = pf['ema'] - self._atrult * pf['atr']
        pf.drop(columns='atr', inplace=True)

    # squeeze挤压，发生在布林带完全进入Keltner通道内部，当布林带再次扩展出Keltner通道时，表示市场将迎来较大的波动。
    def squeeze(self, boll):
        pf = self._pd.get()
        pf['squeeze'] = (
            boll['upper'] < pf['upper_band']) & (
            boll['lower'] > pf['lower_band'])
