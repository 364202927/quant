from server.strategy.base.testCTA import *
from server.strategy.base.testTrade import *
import numpy as np
import pandas as pd

class demoVwap(testCTA, testTrade):
    """VWAP 日内示例策略"""

    def info(self) -> str:
        return "demo + vwap intraday backtest"

    def init(self) -> None:
        self.regTime("1m")
        self.regIndicators({"vwap": "volume.vwap"})
        print("init demoVwap")
        #获取k线,并添加指标
        self._kLine = pdData(read = 'binance_spot_BTCUSDT')
        self._kLine.resample(timeframe = '15m', seTime = ['2023-1-01 00:00:00','2024-01-01 00:00:00'])
        self._indPd = self._kLine.getIndicators(self.vwap)
        # print(self._kLine.get())
        # log(self._indPd.get())
        signal = self.vwap_signal()
        print(signal)

    def vwap_signal(self) -> pd.DataFrame:
        pf = self._indPd.get().copy()
        pf["candle_begin_time"] = pd.to_datetime(pf["candle_begin_time"])
        pf["typical_price"] = (pf["high"] + pf["low"] + pf["close"]) / 3

        trade_day = pf["candle_begin_time"].dt.date
        diff = pf["typical_price"] - pf["vwap"]
        pf["sq_diff"] = diff ** 2
        pf["cum_sq_diff"] = pf["sq_diff"].groupby(trade_day).cumsum()
        day_count = pf.groupby(trade_day).cumcount() + 1
        pf["std"] = np.sqrt(pf["cum_sq_diff"] / day_count)
        pf["upper"] = pf["vwap"] + 2 * pf["std"]
        pf["lower"] = pf["vwap"] - 2 * pf["std"]

        pf["vol_ma5"] = pf["vol"].rolling(5).mean()
        pf["vol_cond"] = pf["vol"] > pf["vol_ma5"] * 1.2

        trade_time = pf["candle_begin_time"].dt.strftime("%H:%M:%S")
        time_mask = (trade_time >= "09:30:00") & (trade_time <= "14:30:00")

        long_entry = (
            (pf["typical_price"] > pf["lower"])
            & (pf["typical_price"].shift(1) <= pf["lower"].shift(1))
            & pf["vol_cond"]
            & time_mask
        )
        short_entry = (
            (pf["typical_price"] < pf["upper"])
            & (pf["typical_price"].shift(1) >= pf["upper"].shift(1))
            & pf["vol_cond"]
            & time_mask
        )

        pf["signal"] = 0
        pf.loc[long_entry, "signal"] = 1
        pf.loc[short_entry, "signal"] = -1

        position = 0
        entry_price = 0.0
        trades: list[dict[str, int | str]] = []
        entry_pos = 0

        for pos, row in pf.iterrows():
            price = float(row["typical_price"])
            time_text = row["candle_begin_time"].strftime("%H:%M:%S")

            if position == 1:
                if price <= float(row["vwap"]) or price <= entry_price * 0.998 or time_text >= "14:50:00":
                    trades.append(
                        {
                            "dir": "long",
                            "open_pos": int(entry_pos),
                            "close_pos": int(pos),
                        }
                    )
                    position = 0
                    continue
            elif position == -1:
                if price >= float(row["vwap"]) or price >= entry_price * 1.002 or time_text >= "14:50:00":
                    trades.append(
                        {
                            "dir": "short",
                            "open_pos": int(entry_pos),
                            "close_pos": int(pos),
                        }
                    )
                    position = 0
                    continue

            if position == 0:
                if row["signal"] == 1:
                    position = 1
                    entry_price = price
                    entry_pos = pos
                elif row["signal"] == -1:
                    position = -1
                    entry_price = price
                    entry_pos = pos

        return pd.DataFrame(trades, columns=["dir", "open_pos", "close_pos"])
        

    def update_1m(self, id: str, timeKey: str) -> None:
        return None
