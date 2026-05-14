from server.strategy.base.testCTA import *
from server.strategy.base.testTrade import *
import numpy as np
# import pandas as pd
from server.utils.science import trend

#todo调试的结构写在testCTA


class demoVwap(testCTA, testTrade):
    """VWAP 日内示例策略"""

    def info(self) -> str:
        return "demo + vwap intraday backtest"

    def init(self) -> None:
        self.regTime("1m")
        self.regIndicators({"vwap": "volume.vwap",
                            # 'ma':'trend.ma',
                            "backTest":"other.backTest"})
        print("init demoVwap")
        # self._kLine = pdData(read = 'binance_spot_BTCUSDT')
        #股市判断牛熊
        # self._kLine.resample(timeframe = '1W', seTime = ['2024-01-01 00:00:00', '2025-01-01 00:00:00'])
        # print(self._kLine.get())
        # trendList = trend(self._kLine.get())
        # print('结果',trendList)
        # for k,v in trendList.items():
        #     if v != None and len(v) > 0:
        #         # print(v[0])
        #         data = v[0]
        #         print(k,":",self._kLine.get(cols = data[0],key= 'candle_begin_time'),'~',self._kLine.get(cols = data[1],key= 'candle_begin_time'))

                # print(k,":",self._kLine.get(cols = v[0],key= 'candle_begin_time'),'~',self._kLine.get(cols = v[1],key= 'candle_begin_time'))
        #策略
        # self.strategyTest('2024-01-01 00:00:00', '2025-01-01 00:00:00')
        # openWeb(3)
        # exit()
    #策略检验
    def strategyTest(self,beginTime,endTime,timeframe = '15m'):
        #获取k线,并添加指标
        # self._kLine = pdData(read = 'binance_spot_BTCUSDT')
        self._kLine.resample(timeframe = timeframe, seTime = [beginTime, endTime])
        _indPd = self._kLine.getIndicators(self.vwap)
        self._signal(_indPd)
        # logFormat(self.getTransaction())
        print("~~~~~~~~~~~~~~",self.getTradesCount())
    
        #计算回测
        self.backTest.delimit(principal = 1000, lv = 1)
        self.backTest.calculate(self._kLine, self.getTransaction())

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
        lv = 10
        self.createTransaction()

        for i in range(len(pf)):
            price = float(prices[i])
            time_text = time_arr[i]
            idx = int(indices[i])
            if position == 1:
                if price <= float(vwaps[i]) or price <= entry_price * 0.998 or time_text >= "14:50:00":
                    # LONG 平仓: sell
                    self.addTransaction(kLong,kSell,lv,idx,100)
                    position = 0
                    continue
            elif position == -1:
                if price >= float(vwaps[i]) or price >= entry_price * 1.002 or time_text >= "14:50:00":
                    # SHORT 平仓: buy
                    self.addTransaction(kShort, kBuy, lv, idx, 100)
                    position = 0
                    continue

            if position == 0:
                if signals[i] == 1:
                    position = 1
                    entry_price = price
                    self.addTransaction(kLong, kBuy, lv, idx, 10)

                elif signals[i] == -1:
                    position = -1
                    entry_price = price
                    self.addTransaction(kShort, kSell, lv, idx, 10)
        

    def update_1m(self, id: str, timeKey: str) -> None:
        return None