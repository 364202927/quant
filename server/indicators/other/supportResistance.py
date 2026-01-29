from server.indicators.baseIndicators import *

# 供需
# https://www.youtube.com/watch?v=eujWFeE3TyE

# 供需，风险管控
# https://www.youtube.com/watch?v=98F_I3toyfc

# 交易介入
# https://www.youtube.com/watch?v=XoD0knVctFk

# 价格行为 入场
# https://www.youtube.com/watch?v=uE7M46rDDPQ


# 横盘大概80跟左右k线，会突破
# 支撑阻力指标用于识别价格的关键水平
# 支撑位：价格反弹的下方价格水平
# 阻力位：价格回落的上方价格水平


class supportResistance(baseIndicators):
    """支撑阻力 (Support & Resistance)

    参数:
    - lookback: 回溯周期，用于计算滚动高低点（默认20）

    基于Pivot点计算:
    - pivot: 轴心点 = (滚动最高 + 滚动最低 + close) / 3
    - support1/resistance1: 第一层支撑/阻力
    - support2/resistance2: 第二层支撑/阻力
    """

    def init(self) -> None:
        self._lookback = 20  # 回溯周期
        self._pd.setHead(['candle_begin_time', 'support1', 'support2', 'resistance1', 'resistance2', 'pivot'])

    def delimit(self, **kwargs) -> None:
        self._lookback = kwargs.get('lookback', self._lookback)

    def calculate(self, pd: pdData) -> 'pdData':
        self._pd.format(pd, style="copy")
        self._computeSR(pd)
        return self._pd

    def calculateTa(self, pd: pdData) -> 'pdData':
        return self.calculate(pd)

    def _computeSR(self, sor_pd: pdData) -> None:
        """计算支撑阻力指标 (自写和talib共用)"""
        pf = self._pd.get()
        # 使用滚动窗口计算高低点
        high = sor_pd['high'].rolling(window=self._lookback).max()
        low = sor_pd['low'].rolling(window=self._lookback).min()
        close = sor_pd['close']

        # Pivot点
        pivot = (high + low + close) / 3
        pf['pivot'] = pivot.round(2)

        # 第一层支撑阻力: S1 = 2*Pivot - High, R1 = 2*Pivot - Low
        support1 = 2 * pivot - high
        resistance1 = 2 * pivot - low
        pf['support1'] = support1.round(2)
        pf['resistance1'] = resistance1.round(2)

        # 第二层支撑阻力: S2 = Pivot - (R1 - S1), R2 = Pivot + (R1 - S1)
        range_sr = resistance1 - support1
        pf['support2'] = (pivot - range_sr).round(2)
        pf['resistance2'] = (pivot + range_sr).round(2)
