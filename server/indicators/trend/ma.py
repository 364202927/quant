from server.indicators.baseIndicators import *


class ma(baseIndicators):
    '移动均线'
    def init(self):
        self.ma = []
        self._pd.setHead(['candle_begin_time'])

    #格式name = {'sma/ema/wma/tema':'均线'}
    def delimit(self, **kWargs):
        for k,v in kWargs.items():
            self.ma.append({k:v})
        
    def calculate(self, pd: pdData) -> pdData:
        self._pd.format(pd, style="copy")
        self._computeMa(pd)
        return self._pd
    def calculateTa(self, pd: pdData) -> pdData:
        self._pd.format(pd, style="copy")
        self._computeMaTa(pd)
        return self._pd

    def _computeMaTa(self, pd: pdData) -> None:
        pf = self._pd.raw()
        close = pd['close'].values
        _ma_map = {'sma': talib.SMA,
            'ema': talib.EMA,
            'wma': talib.WMA,
            'tema': talib.TEMA}
        for ma_item in self.ma:
            for col_name, spec in ma_item.items():
                for ma_type, period in spec.items():
                    fn = _ma_map.get(ma_type)
                    if fn is None:
                        continue
                    pf[col_name] = pd.Series(fn(close, timeperiod=period)).round(2)
    def _computeMa(self, pd: pdData) -> None:
        pf = self._pd.raw()
        close = pd['close']
        for ma_item in self.ma:
            for col_name, spec in ma_item.items():
                for ma_type, period in spec.items():
                    fn = getattr(self, ma_type, None)
                    if fn is None:
                        continue
                    pf[col_name] = round(fn(close, period), 2)

    # 简单移动平均线 (SMA)
    def sma(self, data, period):
        return data.rolling(window=period).mean()
    def ema(self, data, period):
        return data.ewm(span=period, adjust=False).mean()
    def wma(self, data, period):
        weights = np.arange(1, period + 1)
        return data.rolling(period).apply(
            lambda prices: np.dot(
                prices, weights) / weights.sum(), raw=True)
    
    # 三指数移动平均线 (TEMA)
    def tema(self, data, period):
        ema1 = self.ema(data, period)
        ema2 = self.ema(ema1, period)
        ema3 = self.ema(ema2, period)
        return 3 * (ema1 - ema2) + ema3
    
     # sma,ema密集指数
    # def dense(self, strMa):
    #     def dense(row):
    #         if row.isnull().any():
    #             return np.nan
    #         mean = np.mean(row)
    #         res = [abs(1 - num / mean) * 100 for num in row]
    #         return round(sum(res), 2)
    #     ma = self._pd.filter(strMa)
    #     df = ma.apply(dense, axis=1)
    #     return df

        # ma = self._pd.filter(strMa)
        # ma_diffs = ma.diff().abs()
        # ma_diffs_mean = ma_diffs.mean(axis=1)
    # # 判断发散趋势，这里采用简单的比较相邻均值差的方式
        # df = ma_diffs_mean.diff() > 0
        # return df
    # 短周期对长周期交叉0不穿，1上穿，-1下穿   2,3依次为长周期线
    # def cross(self, strMa):
    #     ma = self._pd.filter(strMa)
    #     maList = ma.columns.tolist()
    #     shortMa = self._pd.get(key=maList[0])
    #     #
    #     self._pd.set('crossover', 0)
    #     for icol in range(1, len(ma)):
    #         for i in range(1, len(maList)):
    #             longMa = ma[maList[i]]
    #             if self._pd.get(cols=icol, key='crossover') > 0:  # 如已有交叉，不在检测
    #                 break
    #             # 判断是否交叉
    #             if crossUp(icol, shortMa, longMa):
    #                 self._pd.set('crossover', i, cols=icol)
    #             elif crossDown(icol, shortMa, longMa):
    #                 self._pd.set('crossover', -i, cols=icol)
