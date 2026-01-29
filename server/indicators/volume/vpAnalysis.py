from server.indicators.baseIndicators import *

# 成交量分析 (Volume Profile Analysis)
# 用于分析在不同价格水平上的累积成交量
# 1. 高成交量节点 (HVN) - 表示市场接纳的价格
# 2. 低成交量节点 (LVN) - 表示市场拒绝的价格
# 3. 价值区域 (Value Area) - 70%成交量集中的区域
# 4. Point of Control (POC) - 最高成交量的价格


class vpAnalysis(baseIndicators):
    """成交量分析 (Volume Profile Analysis)

    参数:
    - bins: 价格分组数（默认20）
    - hvnThreshold: HVN阈值倍数（默认1.5，即>1.5倍平均成交量）
    - lvnThreshold: LVN阈值倍数（默认0.5，即<0.5倍平均成交量）
    - valueAreaRatio: 价值区域比例（默认0.7，即70%成交量）

    输出指标:
    - poc: Point of Control，最高成交量的价格
    - hvn: 高成交量节点
    - lvn: 低成交量节点
    - value_area: 价值区域成交量
    """

    def init(self) -> None:
        self._bins = 20             # 价格分组数
        self._hvnThreshold = 1.5    # HVN阈值倍数
        self._lvnThreshold = 0.5    # LVN阈值倍数
        self._valueAreaRatio = 0.7  # 价值区域比例
        self._pd.setHead(['candle_begin_time', 'hvn', 'lvn', 'poc', 'value_area'])

    def delimit(self, **kwargs) -> None:
        self._bins = kwargs.get('bins', self._bins)
        self._hvnThreshold = kwargs.get('hvnThreshold', self._hvnThreshold)
        self._lvnThreshold = kwargs.get('lvnThreshold', self._lvnThreshold)
        self._valueAreaRatio = kwargs.get('valueAreaRatio', self._valueAreaRatio)

    def calculate(self, pd_data: pdData) -> 'pdData':
        self._pd.format(pd_data, style="copy")
        self._computeVp(pd_data)
        return self._pd

    def calculateTa(self, pd_data: pdData) -> 'pdData':
        return self.calculate(pd_data)

    def _computeVp(self, sor_pd: pdData) -> None:
        """计算成交量分析指标 (自写和talib共用)"""
        pf = self._pd.get()
        price_bins = pd.cut(sor_pd['high'].rolling(window=self._bins).max(), bins=self._bins)
        volume_profile = sor_pd.groupby(price_bins)['vol'].sum()
        avg_volume = volume_profile.mean()

        # Point of Control
        poc = volume_profile.idxmax()
        pf['poc'] = float(poc.mid) if hasattr(poc, 'mid') else 0

        # 高成交量节点 (HVN)
        hvn_prices = volume_profile[volume_profile > avg_volume * self._hvnThreshold].index
        pf['hvn'] = float(hvn_prices[len(hvn_prices) // 2].mid) if len(hvn_prices) > 0 else 0

        # 低成交量节点 (LVN)
        lvn_prices = volume_profile[volume_profile < avg_volume * self._lvnThreshold].index
        pf['lvn'] = float(lvn_prices[len(lvn_prices) // 2].mid) if len(lvn_prices) > 0 else 0

        # 价值区域
        sorted_vol = volume_profile.sort_values(ascending=False)
        cumsum = sorted_vol.cumsum()
        value_area_vol = cumsum[cumsum <= sorted_vol.sum() * self._valueAreaRatio].sum()
        pf['value_area'] = float(value_area_vol) if value_area_vol > 0 else 0
