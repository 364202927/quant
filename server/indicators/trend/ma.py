from indicators.baseIndicators import *


class ma(baseIndicators):
    '移动均线'

    _sma, _ema, _wma, _tema = [], [], [], []

    def init(self):
        self._pd.setHead(['candle_begin_time'])

    def delimit(self, **kWargs):
        if kWargs.get('sma'):
            self._sma = kWargs['sma']
        if kWargs.get('ema'):
            self._ema = kWargs['ema']
        if kWargs.get('wma'):
            self._wma = kWargs['wma']
        if kWargs.get('tema'):
            self._tema = kWargs['tema']

    def calculate(self, pd, dense='', crossing=''):
        self._pd.format(pd, style="copy")
        unit = [{'name': "sma_", "v": self._sma, "fn": self.sma},
                {'name': "ema_", "v": self._ema, "fn": self.ema},
                {'name': "wma_", "v": self._wma, "fn": self.wma},
                {'name': "tema_", "v": self._tema, "fn": self.tema}]
        for i in range(len(unit)):
            ind = unit[i]
            if ind['v']:
                for j in ind['v']:
                    lable = ind['name'] + str(j)
                    self._pd.get()[lable] = round(ind['fn'](pd['close'], j), 2)
        # 计算密度
        if dense != '':
            if dense == "esma" or dense == "sema":
                sdf = self.esDense("sma")
                edf = self.esDense("ema")
                self._pd.get()['dense'] = round((sdf + edf) * 0.5, 2)
            else:
                self._pd.get()['dense'] = self.dense(dense)
        # 检测交叉
        if crossing == '':
            return
        self.cross(crossing)

    # 简单移动平均线 (SMA)
    def sma(self, data, period):
        return data.rolling(window=period).mean()
    # 指数移动平均线 (EMA)

    def ema(self, data, period):
        return data.ewm(span=period, adjust=False).mean()
    # 加权移动平均线 (WMA)

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

    def dense(self, strMa):
        def dense(row):
            if row.isnull().any():
                return np.nan
            mean = np.mean(row)
            res = [abs(1 - num / mean) * 100 for num in row]
            return round(sum(res), 2)
        ma = self._pd.filter(strMa)
        df = ma.apply(dense, axis=1)
        return df

        # ma = self._pd.filter(strMa)
        # ma_diffs = ma.diff().abs()
        # ma_diffs_mean = ma_diffs.mean(axis=1)
    # # 判断发散趋势，这里采用简单的比较相邻均值差的方式
        # df = ma_diffs_mean.diff() > 0
        # return df
    # 短周期对长周期交叉0不穿，1上穿，-1下穿   2,3依次为长周期线
    def cross(self, strMa):
        ma = self._pd.filter(strMa)
        maList = ma.columns.tolist()
        shortMa = self._pd.get(key=maList[0])
        #
        self._pd.set('crossover', 0)
        for icol in range(1, len(ma)):
            for i in range(1, len(maList)):
                longMa = ma[maList[i]]
                if self._pd.get(cols=icol, key='crossover') > 0:  # 如已有交叉，不在检测
                    break
                # 判断是否交叉
                if crossUp(icol, shortMa, longMa):
                    self._pd.set('crossover', i, cols=icol)
                elif crossDown(icol, shortMa, longMa):
                    self._pd.set('crossover', -i, cols=icol)
