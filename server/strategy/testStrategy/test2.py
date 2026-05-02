from server.strategy.base.testCTA import *
from datetime import datetime
# import numpy as np

class test2(testCTA):
    """测试用法 - 验证所有指标的自写算法和talib实现"""

    _kLinePd = None  # 原始数据

    def info(self) -> str:
        return "demo+测试代码"

    def init(self) -> None:
        self.regTime('2s', "10s")
        # self._kLinePd = pdData()
        # self._kLinePd.readFile('binance_BTCUSDT.pkl')

        # # print("~~~~init test2~~~~", datetime.now().strftime("%m-%d %H:%M:%S"))
        # # log(self._kLinePd.get())

        # # 注册所有指标
        # self.regIndicators({
        #     'atr': 'oscillators.atr',
        #     'rsi': 'volume.rsi',
        #     'macd': 'volume.macd',
        #     'vwap': 'volume.vwap',
        #     'auctionTheory': 'volume.auctionTheory',
        #     'vpAnalysis': 'volume.vpAnalysis',
        #     'supportResistance': 'other.supportResistance',
        # })

        # # 配置指标参数
        # self.atr.delimit(period=14)
        # self.rsi.delimit(period=14)
        # self.macd.delimit(fast=12, slow=26, signal=9)
        # self.vwap.delimit(period=20)  # 滚动VWAP，0表示累积VWAP
        # self.auctionTheory.delimit(period=20)
        # self.vpAnalysis.delimit(bins=20, hvnThreshold=1.5, lvnThreshold=0.5, valueAreaRatio=0.7)
        # self.supportResistance.delimit(lookback=20)

        # # 计算所有指标
        # pd_data = self._kLinePd.get()
        # self._testIndicators(pd_data)

    def _testIndicators(self, pd_data: pdData) -> None:
        """测试所有指标的自写算法和ta库实现"""
        test_cases = [
            ('atr', self.atr),
            ('rsi', self.rsi),
            ('macd', self.macd),
            ('vwap', self.vwap),
            ('auctionTheory', self.auctionTheory),
            ('vpAnalysis', self.vpAnalysis),
            ('supportResistance', self.supportResistance),
        ]

        for indicator_name, indicator in test_cases:
            self._testIndicator(indicator_name, indicator, pd_data)

    def _testIndicator(self, name: str, indicator, pd_data: pdData) -> None:
        """测试单个指标"""
        print(f"\n========== 测试 {name.upper()} 指标 ==========")

        # 测试自写算法
        custom_df = indicator.calculate(pd_data).get()

        # 测试ta库实现
        ta_df = indicator.calculateTa(pd_data).get()

        print(f"✓ {name} 指标测试完成")
        self._compareResults(custom_df, ta_df)

    def _compareResults(self, custom_df:pdData, ta_df: pdData) -> None:
        """比较自写算法和talib结果的差异"""
        numeric_cols = [col for col in custom_df.columns
                        if col != 'candle_begin_time' and custom_df[col].dtype != 'object']

        for col in numeric_cols:
            custom_vals = custom_df[col].dropna().tail(10).values
            ta_vals = ta_df[col].dropna().tail(10).values

            if len(custom_vals) == 0 or len(ta_vals) == 0:
                continue

            diff = np.abs(custom_vals - ta_vals)
            max_diff, mean_diff = diff.max(), diff.mean()
            status = "✓" if max_diff < 1.0 else "(可接受)"
            print(f"  {col}: 最大差异={max_diff:.6f}, 平均差异={mean_diff:.6f} {status}")

    def update_2s(self, id: str, timeKey: str) -> None:
        pass

    def update_10s(self, id: str, timeKey: str) -> None:
        pass

