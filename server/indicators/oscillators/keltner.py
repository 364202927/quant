from server.indicators.baseIndicators import *
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
        self._maDay = kWargs.get('maDay', self._maDay)
        self._atrult = kWargs.get('atrult', self._atrult)

    def calculate(self, pd: pdData) -> pdData:
        return pdData(data=self._keltnerTrack(pd), style='copy')

    def calculateTa(self, pd: pdData) -> pdData:
        return pdData(data=self._taTrack(pd), style='copy')

    def _keltnerTrack(self, sor_pd: pdData) -> any:
        pf = sor_pd.copy()
        sor_pd = sor_pd.raw()
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
        return pf

    def _taTrack(self, sor_pd: pdData) -> any:
        pf = sor_pd.copy()
        sor_pd = sor_pd.raw()
        close = sor_pd['close'].values
        high, low = sor_pd['high'].values, sor_pd['low'].values
        pf['ema'] = talib.EMA(close, timeperiod=self._maDay)
        tr = talib.TRANGE(high, low, close)
        pf['atr'] = pd.Series(tr).rolling(window=self._maDay).mean()
        pf['upper_band'] = pf['ema'] + self._atrult * pf['atr']
        pf['lower_band'] = pf['ema'] - self._atrult * pf['atr']
        pf.drop(columns='atr', inplace=True)
        return pf

    # squeeze挤压，发生在布林带完全进入Keltner通道内部，当布林带再次扩展出Keltner通道时，表示市场将迎来较大的波动。
    def squeeze(self, boll):
        pf = self._pd.raw()
        pf['squeeze'] = (
            boll['upper'] < pf['upper_band']) & (
            boll['lower'] > pf['lower_band'])
