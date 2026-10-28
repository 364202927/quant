import json
import numpy as np
from server.strategy.base.testCTA import *
from server.utils.science import canOrder

class demoVwap(testCTA):
    """VWAP 日内示例策略"""

    LEVERAGE, MARGIN_PCT = 10, 10               # 下单杠杆 / 单笔占用净值百分比
    SYMBOL, PRINCIPAL = "binance_swap_BTCUSDT", 1000
    SIGNAL_SIGMA = 2.0                          # vwap 通道宽度(σ 倍数)
    SIGNAL_VOL = 1.2                            # 放量阈值(相对5周期均量)
    SIGNAL_SESSION = ("09:30:00", "14:30:00")   # 允许开仓时段(UTC0)

    def info(self) -> str:
        return "demo + vwap intraday backtest"

    async def load(self) -> None:
        # 无regTime则task.bind()返回False,策略不会注册到引擎,web的回测入口就找不到它
        self._testModel(step=100)
        self.regIndicators({
                "vwap": "volume.vwap",
                "backTest": "other.backTest"})
        self.backTest.delimit(principal=self.PRINCIPAL)
        log("~~~~init demoVwap~~~~~~~~")
        self._loadFile(self.SYMBOL, "1h", ["2024-01-01 00:00:00", "2025-01-01 00:00:00"])
        
        self._bf = None
        self._position, self._entry = 0, 0.0

        # self.startStrategy() #快速回测
        # self.beginTest() #隔离回测
    

    # 重置回测数据: 账户/资金费/索引按全量重建(结算时刻是预知元数据, 不取未来价格)
    def _resetTest(self):
        self._trade.initAcc(self._pfAll, self.PRINCIPAL)
        self._position, self._entry, self._bf = 0, 0.0, None
        self._decided = self._startCount - 2  # 首帧100根只决策最新一根(第99根)

    # 信号标记: 在指标数据的副本上打标记(不改动传入数据), 返回 pdData 副本
    def markSignal(self, sorPf):
        bf = pdData()
        bf.format(sorPf.raw(), style="copy")
        pf = bf.raw()
        pf["typical_price"] = (pf["high"] + pf["low"] + pf["close"]) / 3
        sqGrp = ((pf["typical_price"] - pf["vwap"]) ** 2).groupby(pf["candle_begin_time"].dt.date)
        std = np.sqrt(sqGrp.cumsum() / (sqGrp.cumcount() + 1))
        upper, lower = pf["vwap"] + self.SIGNAL_SIGMA * std, pf["vwap"] - self.SIGNAL_SIGMA * std
        volCond = pf["vol"] > pf["vol"].rolling(5).mean() * self.SIGNAL_VOL
        clock = pf["candle_begin_time"].dt.strftime("%H:%M:%S")
        inSession = (clock >= self.SIGNAL_SESSION[0]) & (clock <= self.SIGNAL_SESSION[1])
        longEntry = (pf["typical_price"] > lower) & (pf["typical_price"].shift(1) <= lower.shift(1)) & volCond & inSession
        shortEntry = (pf["typical_price"] < upper) & (pf["typical_price"].shift(1) >= upper.shift(1)) & volCond & inSession
        pf["std"], pf["upper"], pf["lower"] = std, upper, lower
        pf["signal"] = 0
        pf.loc[longEntry, "signal"] = 1
        pf.loc[shortEntry, "signal"] = -1
        self._bf = bf
        return bf

    def startStrategy(self, kLine=None):
        if kLine is None:
            self._quickTest()
            return self.endStrategy()
        pf = self.markSignal(kLine.getIndicators(self.vwap)).raw()
        for idx in range(self._decided + 1, len(pf)):
            self._decide(pf, idx)
        self._decided = len(pf) - 1

        if self.isOver():
            return self.endStrategy()

    # 快速回测: 全量算一次指标+信号, 逐行决策(不建快照)
    def _quickTest(self):
        self._resetTest()
        pf = self.markSignal(self._pfAll.getIndicators(self.vwap)).raw()
        for idx in range(self._startCount - 1, len(pf)):
            self._decide(pf, idx)

    # 单根决策: 只读第 idx 行
    def _decide(self, pf, idx):
        row = pf.iloc[idx]
        price, fill = float(row["typical_price"]), float(row["close"])
        timeText = row["candle_begin_time"].strftime("%H:%M:%S")  # UTC 时钟
        self._trade.checkLiquidation(fill, idx)  # 逐K线按收盘价盯市, 复现 backTest 的逐K线强平检查

        if self._position == 1 and (price <= float(row["vwap"]) or price <= self._entry * 0.998 or timeText >= "14:50:00"):
            # LONG 平仓: sell (14:50 为 UTC 收盘前强平时刻)
            self._trade.closePos(self.SYMBOL, kLong, fill, idx, 100, lv=self.LEVERAGE)
            self._position = 0
            return
        if self._position == -1 and (price >= float(row["vwap"]) or price >= self._entry * 1.002 or timeText >= "14:50:00"):
            # SHORT 平仓: buy
            self._trade.closePos(self.SYMBOL, kShort, fill, idx, 100, lv=self.LEVERAGE)
            self._position = 0
            return
        if self._position != 0 or row["signal"] == 0:
            return
        # 通用下单门禁: 未爆仓 + 在允许时段 + 有可用保证金 (science.canOrder)
        if not canOrder(timeText, self._trade.getAvail(fill), self.SIGNAL_SESSION,
                        self._trade.getAccount()["blowup"]):
            return
        self._position, self._entry = int(row["signal"]), fill
        (self._trade.openLong if self._position == 1 else self._trade.openShort)(self.SYMBOL, fill, idx, self.MARGIN_PCT, lv=self.LEVERAGE)

    # 收尾: 平掉尾仓 + 整段结算 + 打印数据, 返回全结果
    def endStrategy(self):
        if self._bf is None:
            raise RuntimeError("没有可结算的回测数据, 先跑 startStrategy() 或 beginTest()")
        pf = self._bf.raw()
        # 期末仍有持仓按最后一根收盘价平掉, 与 backTest 期末强平口径一致
        self._trade.closePos(self.SYMBOL, "all", float(pf["close"].iloc[-1]), len(pf) - 1, lv=self.LEVERAGE)
        tra = self._trade.getTrajectories()
        summarize = self.backTest.calculateTa(self._bf, self._trade.getRecords())
        print("bf:", self._bf.get())
        print("tra:", tra)
        print("orders:", self._trade.getRecords())
        print("acc:", self._trade.getAccount())
        # 评分里有 ✅❌ 等符号, 转义后再打印, 免得 GBK 控制台直接抛 UnicodeEncodeError
        print("summarize:", summarize)#json.dumps(summarize, ensure_ascii=True, default=str))
        # kLine 用打了signal标记的 bf; tradeRecords 用交易轨迹(前端表格/图表依赖 trades[])
        return {"kLine": self._bf.get(), "tradeRecords": tra, "summarize": summarize}