from server.strategy.base.testCTA import *
from server.strategy.base.testTrade import *
import numpy as np
import pandas as pd

#todo调试的结构写在testCTA


class demoVwap(testCTA, testTrade):
    """VWAP 日内示例策略"""

    def info(self) -> str:
        return "demo + vwap intraday backtest"

    def init(self) -> None:
        self.regTime("1m")
        self.regIndicators({"vwap": "volume.vwap",
                            "backTest":"other.backTest"})
        print("init demoVwap")
        self.strategyTest('2023-1-01 00:00:00', '2024-01-01 00:00:00')
        exit()
    #策略检验
    def strategyTest(self,beginTime,endTime,timeframe = '15m'):
        #获取k线,并添加指标
        self._kLine = pdData(read = 'binance_spot_BTCUSDT')
        self._kLine.resample(timeframe = timeframe, seTime = [beginTime, endTime])
        _indPd = self._kLine.getIndicators(self.vwap)
        signal = self._signal(_indPd) #返回(dir,openIdx,closeIdx)
        logFormat(signal)
        #计算回测
        self.backTest.delimit(principal = 1000, lv = 1)
        self.backTest.calculate(self._kLine, signal)

    def _signal(self, sorPf) -> list:
        pf = sorPf.get()
        pf["typical_price"] = (pf["high"] + pf["low"] + pf["close"]) / 3

        trade_day = pf["candle_begin_time"].dt.date
        sq_grp = ((pf["typical_price"] - pf["vwap"]) ** 2).groupby(trade_day)
        std = np.sqrt(sq_grp.cumsum() / (sq_grp.cumcount() + 1))
        upper = pf["vwap"] + 2 * std
        lower = pf["vwap"] - 2 * std

        vol_cond = pf["vol"] > pf["vol"].rolling(5).mean() * 1.2

        trade_time = pf["candle_begin_time"].dt.strftime("%H:%M:%S")
        time_mask = (trade_time >= "09:30:00") & (trade_time <= "14:30:00")

        long_entry = ((pf["typical_price"] > lower)
            & (pf["typical_price"].shift(1) <= lower.shift(1))
            & vol_cond
            & time_mask )
        short_entry = ((pf["typical_price"] < upper)
            & (pf["typical_price"].shift(1) >= upper.shift(1))
            & vol_cond
            & time_mask)

        pf["signal"] = 0
        pf.loc[long_entry, "signal"] = 1
        pf.loc[short_entry, "signal"] = -1

        prices = pf["typical_price"].to_numpy()
        vwaps = pf["vwap"].to_numpy()
        signals = pf["signal"].to_numpy()
        time_arr = trade_time.to_numpy()
        indices = pf.index.to_numpy()

        position = 0
        entry_price = 0.0
        trajectories: list[dict] = []
        current: dict | None = None
        lv = 10

        for i in range(len(pf)):
            price = float(prices[i])
            time_text = time_arr[i]
            idx = int(indices[i])

            if position == 1:
                if price <= float(vwaps[i]) or price <= entry_price * 0.998 or time_text >= "14:50:00":
                    # LONG 平仓: sell
                    current["trades"].append({"behavior": kSell, "pos": idx, "lv": lv, "position%": 100})
                    trajectories.append(current)
                    current, position = None, 0
                    continue
            elif position == -1:
                if price >= float(vwaps[i]) or price >= entry_price * 1.002 or time_text >= "14:50:00":
                    # SHORT 平仓: buy
                    current["trades"].append({"behavior": kBuy, "pos": idx, "lv": lv, "position%": 100})
                    trajectories.append(current)
                    current, position = None, 0
                    continue

            if position == 0:
                if signals[i] == 1:
                    position = 1
                    entry_price = price
                    # LONG 开仓: buy, 首 action 仓位 10%
                    current = {"dir": kLong, "trades": [{"behavior": kBuy, "pos": idx, "lv": lv, "position%": 10}]}
                elif signals[i] == -1:
                    position = -1
                    entry_price = price
                    # SHORT 开仓: sell, 首 action 仓位 10%
                    current = {"dir": kShort, "trades": [{"behavior": kSell, "pos": idx, "lv": lv, "position%": 10}]}

        return trajectories
        

    def update_1m(self, id: str, timeKey: str) -> None:
        return None
