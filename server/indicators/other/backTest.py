import math
import operator as op
from bisect import bisect_right
from collections import defaultdict
import numpy as np
import pandas as pd
from server.indicators.baseIndicators import *
from server.utils import switch, switchFn
from server.utils.science import (kFeeRate, kLiqRatio, kMarginRatio,feeCost, fundingPay, fundingTable, slipPrice, slipRange)
from server.market import kLong, kShort, kBuy, kSell, kSpot

"""
结构: 一、统计指标 → 二、评分规则 → 三、事件驱动撮合 → 四、backTest 类
约定:
 - 时间轴: 事件时间 = 成交时刻。轨迹事件 = pos 所在K线的收盘时刻(=下一根开盘,可再叠加 exec_delay 根),价格取该K线 close;
   记录事件 = 成交所在K线的开盘时间戳,价格取记录里的成交价。同一时刻先结算资金费、再处理事件:
   边界上开仓不计该次资金费、平仓计入(实盘成交晚于结算快照)
 - 检查点之间按半开区间 [prev, ts) 逐K线用 low/high 检查强平。期间 cash/持仓不变,nav 对价格线性,最差点必在 low/high 之一
 - 强平两层: 破产闸门 nav < 本金*kLiqRatio(策略失效); 维持保证金 nav < kMaintRatio*Σ永续名义(现货不适用)
 - 成交口径两种: 轨迹回测(calculate,基准口径)按 close+滑点+手续费模型折算; 记录回测(calculateTa)直接用记录里的成交价/数量/保证金/手续费
   记录字段口径以 calculate 为准: total=USDT 保证金(=amount*average/leverage), fee(BNB)=USDT 等值手续费
 - 资金费按 8h(UTC 00/08/16)结算,取结算K线的 open 价,多头付正费率、空头收正费率(两种口径一致)
 - 保证金采用全仓、不做多空轧差(对冲仓位各自占用保证金,偏保守)
 - 年化周期数 ppy 只存于 backTest(delimit 的 periods,默认 365,股票改 252),统计函数一律不传 ppy
 - 股票: K线无 funding_bps 列即不计资金费; 允许休市缺口(轨迹事件时间=K线开盘+bar 时长,日线即当日收盘); type 属于 _CASH_TYPES 的不计资金费/维持保证金
 - K线缺口不再报错,只在 params.kline_gaps 回显; 加密结算K线缺失时 science.fundingTable 用 asof(前一根)兜底
 - 强平遇跳空(开盘价已越过触发价)按开盘价成交,不再乐观地取触发价
 - 手续费/滑点/资金费/杠杆/强平的常量与算法统一在 science.py,与 testTrade 共用
"""

_CASH_TYPES = (kSpot, "stock")  # 无资金费、无维持保证金强平的品种;股票的 type 值加在这里
kMaintRatio = 0.005  # 永续维持保证金率(占名义价值)。占位值:应移入 science.py,并按币种/分档及 PM 的 uniMMR 规则核实

# ======== 一、统计指标 ========
def sharpe(returns: np.ndarray) -> float:  # 单周期夏普,年化由 backTest 乘 sqrt(ppy)
    std = np.std(returns, ddof=1) if len(returns) > 1 else 0.0
    return float(np.mean(returns) / std) if std > 0 else 0.0


def calmar(cagr_val: float, max_dd: float) -> float:  # 回撤为 0 且赚钱 → 封顶 999;不赚钱 → 0
    return min(cagr_val / abs(max_dd), 999.0) if max_dd else 999.0 * (cagr_val > 0)


def max_drawdown(nav: np.ndarray) -> float:
    """nav 须包含初始权益点,否则首段回撤会被漏掉"""
    peak = np.maximum.accumulate(nav)
    return float(((nav - peak) / peak).min())


def cvar(returns: np.ndarray, alpha: float) -> float:
    return float(returns[returns <= np.percentile(returns, alpha * 100)].mean())


def profit_factor(pnl: np.ndarray) -> float:
    loss = -pnl[pnl < 0].sum()
    return min(float(pnl[pnl > 0].sum() / loss), 999.0) if loss > 0 else 999.0


def trimmed_profit(pnl: np.ndarray, top_frac: float = 0.05) -> float:
    """剔除最赚钱的 top_frac 笔(至少1笔)后的总盈亏,衡量利润是否依赖少数极端单"""
    k = max(1, math.ceil(len(pnl) * top_frac))
    return float(np.sort(pnl)[:-k].sum())


def deflated_sharpe_pval(returns: np.ndarray, n_trials: int, n_sim: int = 1000, seed: int = 42) -> float:
    """H0: 真实夏普为 0。n_trials 次独立试验的最大夏普 ≥ 观测夏普的概率(单周期口径,与年化无关)"""
    n = len(returns)
    sr_obs = sharpe(returns)
    if n < 10 or sr_obs == 0.0:
        return 1.0
    rng = np.random.default_rng(seed)
    zero_mean = returns - returns.mean()
    max_sr = np.empty(n_sim)
    for i in range(n_sim):
        batch = zero_mean[rng.integers(0, n, size=(n_trials, n))]
        std = batch.std(axis=1, ddof=1)
        sr = np.divide(batch.mean(axis=1), std, out=np.zeros(n_trials), where=std > 0)
        max_sr[i] = sr.max()
    return float(np.mean(max_sr >= sr_obs))


# ======== 二、评分规则 ========
_GT, _GE, _LT, _LE = op.gt, op.ge, op.lt, op.le
# (指标分区, 指标名, ((比较, 阈值, 得分, 文案), ...) 按序首个命中, 未命中文案)  未命中得 0 分
_RULES = (
    # ---- 盈利 25 ----
    ("return_quality", "total_return_pct", ((_GT, 0, 5, "总收益为正"),), "总收益 ≤ 0 (策略未产生正回报)"),
    ("overfit_filter", "sharpe_ratio", ((_GT, 1, 10, "夏普 > 1 (风险调整后收益优秀)"), (_GT, 0, 5, "夏普 0~1 (勉强为正)")), "夏普 ≤ 0 (风险调整后无超额收益)"),
    ("overfit_filter", "calmar_ratio", ((_GT, 1, 10, "卡玛 > 1 (相对回撤收益好)"), (_GT, 0, 5, "卡玛 0~1")), "卡玛 ≤ 0 (收益/回撤无吸引力)"),
    # ---- 风险 20 (回撤/CVaR 单位为 %,波动率为小数) ----
    ("live_tolerance", "max_drawdown_pct", ((_LT, 10, 8, "最大回撤 < 10%"), (_LT, 20, 4, "最大回撤 10%~20%")), "最大回撤 ≥ 20% (实盘压力大)"),
    ("post_cost_survival", "cvar_95_pct", ((_LE, 2, 6, "日 CVaR95 ≤ 2% (尾部风险小)"), (_LE, 5, 3, "日 CVaR95 2%~5%")), "日 CVaR95 > 5% (极端日亏损大)"),
    ("post_cost_survival", "daily_volatility", ((_LT, 0.01, 6, "日波动率 < 1%"), (_LT, 0.03, 3, "日波动率 1%~3%")), "日波动率 ≥ 3% (净值起伏过大)"),
    # ---- 过拟合 20 ----
    ("overfit_filter", "deflated_sharpe_pvalue", ((_LE, 0.05, 12, "Deflated Sharpe p ≤ 0.05 (非数据窥探)"),), "Deflated Sharpe p > 0.05 (高夏普可能是噪声)"),
    ("live_tolerance", "oos_sharpe_change", ((_GE, -0.3, 8, "后半段夏普衰减 < 30% (时间稳定)"), (_GE, -0.5, 4, "后半段夏普衰减 30%~50%")), "后半段夏普衰减 > 50% 或无法计算 (前强后弱)"),  # (后半段-前半段)/|前半段|,负=变差
    # ---- 稳健 15 ----
    ("return_quality", "profit_factor", ((_GE, 1.5, 8, "盈利因子 ≥ 1.5"), (_GE, 1.1, 4, "盈利因子 1.1~1.5")), "盈利因子 < 1.1 (盈亏结构薄)"),
    ("return_quality", "trimmed_profit", ((_GT, 0, 7, "剔除最赚 5% 交易后仍盈利"),), "剔除最赚 5% 交易后亏损 (利润依赖少数极端单)"),
    # ---- 实盘摩擦 20 ----
    ("live_tolerance", "cost_breakeven_multiple", ((_GE, 3, 12, "成本放大 ≥ 3 倍才归零 (抗成本恶化)"), (_GE, 2, 6, "成本放大 2~3 倍归零")), "成本放大 < 2 倍即归零 (实盘危险)"),  # 成本放大几倍后利润归零
    ("basic", "n_trades", ((_GE, 100, 8, "交易数 ≥ 100"), (_GE, 30, 4, "交易数 30~100")), "交易数 < 30 (统计置信度低)"),
)

_VERDICT = {
    "no_trades": "⚠️ 无有效交易 (未产生任何成交信号，无法评分)",
    "insufficient_sample": "⚠️ 样本不足 (交易数或天数过少，指标不可信)",
    "blowup": "💥 爆仓 (资金跌破清算线，策略失效)",
    "live": "✅ 可实盘 (总分 ≥ 70)",
    "improve": "🔧 继续改善 (总分 40~69)",
    "discard": "❌ 尽早放弃 (总分 < 40)",
}


def score(metrics: dict) -> dict:
    basic = metrics["basic"]
    gate = switch(_VERDICT, basic["status"])  # status=ok 时无对应键 → False
    if gate:
        return {"total_score": 0, "verdict": gate, "details": [gate]}
    total, details = 0, []
    for section, field, tiers, miss in _RULES:
        value = metrics[section][field]
        value = np.nan if value is None else value  # None=无法计算,所有比较为 False → 0 分
        pts, desc = next(((p, d) for cmp, thr, p, d in tiers if cmp(value, thr)), (0, miss))
        total += pts
        details.append(f"{desc} → +{pts}")
    tier = "blowup" if basic["blowup"] else ("discard", "improve", "live")[bisect_right((40, 70), total)]
    return {"total_score": total, "verdict": switch(_VERDICT, tier), "details": details}


# ======== 三、事件驱动撮合 ========
EPS = 1e-8
_SIDE = {kLong: 1, kShort: -1}  # 方向 -> 盈亏符号
_KIND = {f"{kLong}:{kBuy}": "open", f"{kLong}:{kSell}": "close", f"{kShort}:{kSell}": "open", f"{kShort}:{kBuy}": "close"}
TRADE_COLS = ["traj_id", "side", "open_time", "close_time", "duration", "qty", "entry", "exit", "margin", "fee", "pnl", "exit_kind"]


def check_kline(df: pd.DataFrame) -> None:
    """df 以 candle_begin_time(UTC,无时区)为索引。有问题直接抛错并给出首个异常行"""
    if len(df) < 2:
        raise ValueError("K线至少需要 2 根")
    bad = df[[c for c in ("open", "high", "low", "close", "funding_bps") if c in df.columns]].isna().any(axis=1)  # 股票无 funding_bps
    if bad.any():
        raise ValueError(f"K线含 NaN,首个异常行:\n{df[bad].head(1)}")
    if not (df.index.is_unique and df.index.is_monotonic_increasing):
        raise ValueError("K线时间必须唯一且递增")
    if df.index.tz is not None:
        raise ValueError("raw() 应为 UTC 无时区时间")
    ohlc = df[["open", "high", "low", "close"]]
    bad = (df["high"] < ohlc.max(axis=1)) | (df["low"] > ohlc.min(axis=1))
    if bad.any():
        raise ValueError(f"K线 high/low 与 open/close 矛盾,首个异常行:\n{df[bad].head(1)}")


def barStep(index: pd.DatetimeIndex) -> pd.Timedelta:
    """K线时长 = 相邻最小间隔(休市/缺K线只会让间隔变大)"""
    return index.to_series().diff().min()


def build_trace_events(df: pd.DataFrame, signal: list, delay: int = 0) -> list:
    """交易轨迹 -> 全局事件队列。同一时刻先平后开(释放的保证金可立即复用)
    轨迹只给仓位比例(pct)与杠杆(lv),成交价/数量/保证金/手续费留空,由 Account 按滑点模型折算
    事件时间 = 第 pos+delay 根K线的收盘时刻,价格取该K线 close;delay>0 用于成交延迟压力测试"""
    times, close, n = df.index, df["close"].to_numpy(), len(df)
    step = barStep(times)
    events = []
    for tid, traj in enumerate(signal):
        trades = traj["trades"]
        if not trades:  # 没有任何成交的轨迹直接跳过
            continue
        side, pos = switch(_SIDE, traj["dir"]), [t["pos"] for t in trades]
        if not side or any(b <= a for a, b in zip(pos, pos[1:])) or pos[0] < 0 or pos[-1] + delay >= n:
            raise ValueError(f"轨迹 {tid} 非法: dir={traj['dir']}, pos={pos}, exec_delay={delay} (dir 需合法, pos 严格递增且 0 ≤ pos+exec_delay < K线数 {n})")
        for t in trades:
            kind = switch(_KIND, f"{traj['dir']}:{t['behavior']}")
            if not kind:
                raise ValueError(f"轨迹 {tid}: behavior={t['behavior']} 与 dir={traj['dir']} 不匹配")
            pct, lv = float(t.get("position%", 10)) / 100.0, float(t.get("lv", 1))
            if not (pct > 0 and lv > 0):  # 同时拦住 NaN
                raise ValueError(f"轨迹 {tid} 的 position%/lv 非法: {t}")
            i = t["pos"] + delay
            events.append({"time": times[i] + step, "traj_id": tid, "side": side, "kind": kind, "pct": pct,
                           "lv": lv, "price": float(close[i]), "qty": None, "margin": None, "fill": None,
                           "perp": traj.get("type") not in _CASH_TYPES, "last": t is trades[-1]})
    events.sort(key=lambda e: (e["time"], e["kind"] == "open", e["traj_id"]))
    return events


def build_record_events(df: pd.DataFrame, records: list) -> list:
    """交易记录 -> 全局事件队列。成交价/数量/保证金/手续费直接取记录(fill),Account 不再重算
    字段口径以 calculate 为准: amount=数量, average=成交价, total=USDT 保证金, fee(BNB)=USDT 等值手续费, leverage=杠杆
    按 (symbol, 方向) 分组,组序号即 traj_id;资金费仍按 K 线结算,记录里的 funding 行不重复计入现金
    记录的 time 为该笔成交所在 K 线下标: 事件时间取该K线开盘时间戳(成交晚于同刻的资金费结算),事件价格取记录成交价"""
    times, n, groups, events = df.index, len(df), {}, []
    for rec in records:
        if rec.get("kind") not in ("open", "close"):
            continue
        side = switch(_SIDE, rec.get("positionSide"))
        if not side:
            raise ValueError(f"交易记录 positionSide 非法: {rec}")
        qty, px = float(rec["amount"]), float(rec["average"])
        if not (qty > 0 and px > 0 and 0 <= rec["time"] < n):
            raise ValueError(f"交易记录 amount/average/time 非法: {rec}")
        trajId = groups.setdefault((rec["symbol"], side), len(groups))
        events.append({"time": times[rec["time"]], "traj_id": trajId, "side": side, "kind": rec["kind"], "pct": None,
                       "lv": float(rec["leverage"]), "price": px, "qty": qty,
                       "margin": float(rec["total"]), "fill": (px, float(rec["fee(BNB)"])),
                       "perp": rec.get("type") not in _CASH_TYPES, "last": False})
    events.sort(key=lambda e: (e["time"], e["kind"] == "open", e["traj_id"]))
    for e in {e["traj_id"]: e for e in events}.values():  # 排序后,每组时间上最后一条事件负责平掉残仓
        e["last"] = True
    return events


class Account:
    """共享账户。cash=已实现权益(含手续费/资金费),净值=cash+全部持仓浮盈
    成交口径: 事件带 fill(成交价,手续费)时直接用(记录回测),否则按滑点+手续费模型折算(轨迹回测)
    """

    def __init__(self, equity: float, fee_rate: float, slip: list, liq_ratio: float, mmr: float):
        self.equity0, self.cash, self.fee_rate, self.floor, self.mmr = equity, equity, fee_rate, equity * liq_ratio, mmr
        self.slip_lo, self.slip_hi, seed = slip
        self.rng = np.random.default_rng(int(seed))
        self.positions, self.trades, self.troughs = {}, [], []  # (traj_id, side) -> 持仓; troughs=[(时间, 未触发强平K线内最差净值)]
        self.fee_open = self.fee_close = self.slip_cost = self.funding_cost = self.max_margin = 0.0
        self.skipped, self.blown, self.blown_at = 0, False, None

    # ---- 状态 ----
    def used_margin(self) -> float:
        return sum(p["margin"] for p in self.positions.values())

    def exposure(self) -> tuple:
        """(净敞口 E, 成本项 C, 永续总数量 Q): nav(p) = cash - C + E*p,对价格线性"""
        E = C = Q = 0.0
        for p in self.positions.values():
            signed = p["qty"] * p["side"]
            E, C, Q = E + signed, C + signed * p["cost"], Q + p["qty"] * p["perp"]
        return E, C, Q

    def nav(self, price: float) -> float:
        E, C, _ = self.exposure()
        return self.cash - C + E * price

    # ---- 成交口径 ----
    def _openFill(self, e: dict):
        """返回 (成交价, 数量, 保证金, 手续费);模型口径下可用保证金不足返回 None"""
        if e["fill"] is not None:
            return e["fill"][0], e["qty"], e["margin"], e["fill"][1]
        nav = self.nav(e["price"])
        margin = min(nav * e["pct"], nav - self.used_margin())  # 不得超过可用保证金
        if margin <= EPS:
            return None
        px = slipPrice(e["price"], e["side"], self.rng.uniform(self.slip_lo, self.slip_hi))
        qty = margin * e["lv"] / px
        return px, qty, margin, feeCost(qty, px, self.fee_rate)

    def _closeFill(self, price: float, side: int, qty: float):
        px = slipPrice(price, -side, self.rng.uniform(self.slip_lo, self.slip_hi))
        return px, feeCost(qty, px, self.fee_rate)

    # ---- 事件 ----
    def on_event(self, e: dict) -> None:
        if self.blown:
            return
        switchFn({"open": self._open, "close": self._close}, e["kind"], e=e)
        key = (e["traj_id"], e["side"])
        if e["last"] and key in self.positions:  # 轨迹最后一个事件后仍有残仓 → 按该事件价强平
            self._exit(key, self.positions[key]["qty"], e["price"], e["time"], "traj_end")
        self._check_liquidation(e["time"], e["price"])

    def _open(self, e: dict) -> None:
        fill = self._openFill(e)
        if fill is None:  # 可用保证金不足,放弃该开仓
            self.skipped += 1
            return
        px, qty, margin, fee = fill
        pos = self.positions.setdefault((e["traj_id"], e["side"]), {"side": e["side"], "traj_id": e["traj_id"], "opened_at": e["time"], "qty": 0.0, "cost": 0.0, "margin": 0.0, "fee": 0.0, "perp": e["perp"]})
        pos["cost"] = (pos["qty"] * pos["cost"] + qty * px) / (pos["qty"] + qty)
        pos["qty"] += qty
        pos["margin"] += margin
        pos["fee"] += fee
        self.cash -= fee
        self.fee_open += fee
        self.slip_cost += abs(px - e["price"]) * qty  # 轨迹口径=滑点成本;记录口径事件价即成交价,恒为 0
        self.max_margin = max(self.max_margin, self.used_margin())

    def _close(self, e: dict) -> None:
        key = (e["traj_id"], e["side"])
        pos = self.positions.get(key)
        if pos is None:  # 对应开仓被保证金约束拒绝,或记录本身无持仓
            return
        qty = pos["qty"] * min(e["pct"], 1.0) if e["qty"] is None else min(e["qty"], pos["qty"])
        self._exit(key, qty, e["price"], e["time"], "signal", e["fill"])

    def _exit(self, key: tuple, qty: float, price: float, ts, kind: str, fill=None) -> None:
        pos, side = self.positions[key], key[1]
        frac = qty / pos["qty"]
        px, fee_close = fill if fill is not None else self._closeFill(price, side, qty)
        fee_open, margin = pos["fee"] * frac, pos["margin"] * frac
        gross = (px - pos["cost"]) * qty * side
        self.cash += gross - fee_close
        self.fee_close += fee_close
        self.slip_cost += abs(px - price) * qty
        pos["qty"] -= qty
        pos["fee"] -= fee_open
        pos["margin"] -= margin
        self.trades.append(
            {
                "traj_id": key[0],
                "side": side,
                "open_time": pos["opened_at"],
                "close_time": ts,
                "duration": int((ts - pos["opened_at"]).total_seconds() // 60),
                "qty": qty,
                "entry": pos["cost"],
                "exit": px,
                "margin": margin,
                "fee": fee_open + fee_close,
                "pnl": gross - fee_open - fee_close,
                "exit_kind": kind,
            }
        )
        if pos["qty"] <= EPS:
            del self.positions[key]

    def flatten(self, ts, price: float, kind: str) -> None:
        for key in list(self.positions):
            self._exit(key, self.positions[key]["qty"], price, ts, kind)

    def sweep(self, times, opens: np.ndarray, lows: np.ndarray, highs: np.ndarray) -> None:
        """两个检查点之间逐K线用 low/high 检查强平。期间 cash/持仓不变,slack(p)=a+b*p 对价格线性:
        b≥0(净多)最差点在 low,b<0 在 high。强平价取 slack=0 的穿越价,若开盘已越过则按开盘价(跳空),最后夹到 [low, high]"""
        if self.blown or not self.positions or len(times) == 0:
            return
        E, C, Q = self.exposure()
        base = self.cash - C  # nav(p) = base + E*p
        legs = [(base - self.floor, E)]  # 破产闸门: nav < floor
        if Q > 0:
            legs.append((base, E - self.mmr * Q))  # 维持保证金: nav < mmr*Q*p
        worst = [np.where(b >= 0, lows, highs) for _, b in legs]
        hit = np.flatnonzero(np.any([a + b * w < 0 for (a, b), w in zip(legs, worst)], axis=0))
        stop = hit[0] if hit.size else len(times)
        if stop:  # 未触发K线内的最差净值,供逐K最大回撤
            navw = base + E * worst[0][:stop]
            j = int(np.argmin(navw))
            self.troughs.append((times[j], float(navw[j])))
        if not hit.size:
            return
        i = hit[0]
        cands = [-a / b if b else w[i] for (a, b), w in zip(legs, worst) if a + b * w[i] < 0]
        px = max(cands) if E >= 0 else min(cands)  # 净多按下跌先触发,净空按上涨先触发
        px = float(np.clip(min(px, opens[i]) if E >= 0 else max(px, opens[i]), lows[i], highs[i]))  # 跳空: 开盘价已越过触发价
        self.flatten(times[i], px, "liquidation")
        self.blown, self.blown_at = True, times[i]

    def settle_funding(self, ts, price: float, rate: float) -> None:
        if self.blown:
            return
        cost = sum(fundingPay(p["qty"], price, rate, p["side"]) for p in self.positions.values() if p["perp"] and p["opened_at"] < ts)
        self.cash -= cost
        self.funding_cost += cost
        self._check_liquidation(ts, price)

    def _check_liquidation(self, ts, price: float) -> None:
        E, C, Q = self.exposure()
        nav = self.cash - C + E * price
        if nav < self.floor or nav < self.mmr * Q * price:
            self.flatten(ts, price, "liquidation")
            self.blown, self.blown_at = True, ts


def run_portfolio(df: pd.DataFrame, events: list, acct: Account):
    """用给定账户重放事件,返回 (trades_df, curve_df[time,equity], summary)
    curve 含初始点、逐日收盘净值、期末平仓后净值; summary['troughs'] 为未触发强平K线内的最差净值(逐K最大回撤用)"""
    idx, close, step = df.index, df["close"], barStep(df.index)
    opens, lows, highs = df["open"].to_numpy(), df["low"].to_numpy(), df["high"].to_numpy()
    settle = fundingTable(df)  # 缺结算K线会直接 KeyError
    day_end = {t + step: t for t in idx.to_series().groupby(idx.normalize()).last()}  # 当日收盘时刻 -> 当日最后一根K线(曲线按它打点)
    by_time = defaultdict(list)
    for e in events:
        by_time[e["time"]].append(e)

    curve, prev = [(idx[0], acct.equity0)], idx[0]
    for ts in sorted(set(settle) | set(day_end) | set(by_time)):
        lo, hi = idx.searchsorted([prev, ts])  # 半开区间 [prev, ts)
        acct.sweep(idx[lo:hi], opens[lo:hi], lows[lo:hi], highs[lo:hi])
        prev = ts
        if ts in settle:
            acct.settle_funding(ts, *settle[ts])
        for e in by_time.get(ts, ()):
            acct.on_event(e)
        if acct.blown:
            curve.append((acct.blown_at, acct.cash))
            break
        if ts in day_end:
            curve.append((day_end[ts], acct.nav(close.at[day_end[ts]])))
    if not acct.blown:  # 期末仍有持仓 → 按最后一根收盘价平仓(计入手续费/滑点)
        acct.flatten(idx[-1] + step, close.iloc[-1], "end")
        curve.append((idx[-1], acct.nav(close.iloc[-1])))

    curve_df = pd.DataFrame(curve, columns=["time", "equity"]).drop_duplicates("time", keep="last")
    lvs = [e["lv"] for e in events if e["kind"] == "open"] or [1.0]
    summary = {
        "initial_equity": acct.equity0,
        "final_equity": float(curve_df["equity"].iloc[-1]),
        "fee_total": acct.fee_open + acct.fee_close,
        "slip_cost": acct.slip_cost,
        "funding_cost": acct.funding_cost,
        "max_margin_used": acct.max_margin,
        "skipped_opens": acct.skipped,
        "avg_leverage": float(np.mean(lvs)),
        "blowup": acct.blown,
        "blowup_time": acct.blown_at,
        "troughs": pd.Series([v for _, v in acct.troughs], index=pd.DatetimeIndex([t for t, _ in acct.troughs]), dtype=float),
    }
    return pd.DataFrame(acct.trades, columns=TRADE_COLS), curve_df, summary


# ======== 四、回测类 ========
class backTest(baseIndicators):
    "回测数据：性能测试"

    MIN_TRADES, MIN_DAYS = 10, 30  # MIN_DAYS 同时保证前/后半段夏普各有 ≥15 个日收益

    def init(self):
        self.principal = 1000
        self.margin = self.principal * kMarginRatio  # 起始权益
        self.fee_rate = kFeeRate  # 单边吃单手续费率
        self.slip = slipRange()  # [slip_min, slip_max, seed]
        self.ppy = 365.0  # 年化周期数(加密货币全年开盘=365;股票改 252)
        self.n_trials = 100  # Deflated Sharpe 的试验次数,应传优化器真实试验数
        self.exec_delay = 0  # 轨迹成交延迟K线数(压力测试用)

    def delimit(self, **kWargs):
        """principal=本金, fee_rate=手续费率, slip=[min,max,seed], periods=年化周期数(默认365), n_trials=DSR试验次数(默认100),
        exec_delay=轨迹成交延迟K线数(默认0)。None/缺省项保持当前值或 science 默认,杠杆由信号 lv 决定,缺省 1"""
        self.principal = kWargs.get("principal") or self.principal
        self.margin = self.principal * kMarginRatio
        self.fee_rate = kWargs.get("fee_rate", self.fee_rate)
        self.slip = slipRange(kWargs["slip"]) if kWargs.get("slip") else self.slip
        self.ppy = float(kWargs.get("periods") or self.ppy)
        self.n_trials = int(kWargs.get("n_trials") or self.n_trials)
        delay = kWargs.get("exec_delay")
        self.exec_delay = self.exec_delay if delay is None else int(delay)

    # 入口一 交易轨迹(getTrajectories,基准口径):只给仓位比例,成交价/费用按滑点与手续费模型折算
    def calculate(self, kLine, signal: list) -> dict:
        return self._run(kLine, lambda df, src: build_trace_events(df, src, self.exec_delay), signal)

    # 入口二 交易记录(getRecords,辅助):直接用记录里的成交价/数量/保证金/手续费(USDT)
    def calculateTa(self, kLine, records: list) -> dict:
        return self._run(kLine, build_record_events, records)

    # 两条入口共用同一套撮合/统计/评分
    def _run(self, kLine, builder, source: list) -> dict:
        df = kLine.raw().set_index("candle_begin_time")  # raw() 为 UTC0 无时区;回测按 UTC 结算资金费
        check_kline(df)
        acct = Account(self.margin, self.fee_rate, self.slip, kLiqRatio, kMaintRatio)
        trades, curve, summary = run_portfolio(df, builder(df, source), acct)
        result = self._testing(trades, curve, summary)
        result["score"] = score(result)
        result["params"] = {"fee_rate": self.fee_rate, "slip": list(self.slip), "periods": self.ppy, "n_trials": self.n_trials,
                            "exec_delay": self.exec_delay, "liq_ratio": kLiqRatio, "maint_ratio": kMaintRatio,
                            "kline_gaps": int((df.index.to_series().diff() > barStep(df.index)).sum())}  # 回显口径与K线缺口数(股票含休市),便于复现与对比
        return result

    def _testing(self, trades, curve, summary: dict) -> dict:
        daily = curve.set_index("time")["equity"].resample("D").last().dropna()  # 无数据的日子不补0收益(股票休市)
        n_trades, n_days = len(trades), len(daily)
        thin = n_trades < self.MIN_TRADES or n_days < self.MIN_DAYS
        status = "no_trades" if not n_trades else ("blowup" if summary["blowup"] else "insufficient_sample") if thin else "ok"  # 爆仓优先于样本不足
        blowup_time = None if summary["blowup_time"] is None else str(summary["blowup_time"])
        if status != "ok":
            return {"basic": {"status": status, "n_trades": n_trades, "trading_days": n_days, "blowup": summary["blowup"], "blowup_time": blowup_time},
                    "overfit_filter": {}, "post_cost_survival": {}, "return_quality": {}, "live_tolerance": {}}

        init_eq, final_eq = summary["initial_equity"], summary["final_equity"]
        net = final_eq - init_eq
        nav = np.r_[init_eq, daily.to_numpy()]  # 含初始点,首日损益不丢
        ret = np.diff(nav) / nav[:-1]
        pnl = trades["pnl"].to_numpy()
        path = pd.concat([summary["troughs"], curve.set_index("time")["equity"]]).sort_index(kind="mergesort")  # 同刻最差点在前,逐K最大回撤
        max_dd = max_drawdown(np.r_[init_eq, path.to_numpy()])
        cagr_val = (final_eq / init_eq) ** (self.ppy / n_days) - 1.0 if final_eq > 0 else 0.0
        dsr_p = deflated_sharpe_pval(ret, self.n_trials)
        daily_vol = float(np.std(ret, ddof=1))

        mid = len(ret) // 2  # 按时间前/后半段对比夏普(比值与年化无关)
        is_sr, oos_sr = sharpe(ret[:mid]), sharpe(ret[mid:])
        oos_change = (oos_sr - is_sr) / is_sr if is_sr > 0 else None  # 前半段夏普 ≤ 0 时稳定性无意义

        # 成本压力:费用+滑点+资金费(仅付出部分)整体放大 k 倍,k=breakeven 时利润归零
        cost = summary["fee_total"] + summary["slip_cost"] + max(summary["funding_cost"], 0.0)
        wins, losses = pnl[pnl > 0], pnl[pnl < 0]
        avg_loss = losses.mean() if len(losses) else 0.0

        return {
            "basic": {
                "status": "ok",
                "margin": round(final_eq, 2),
                "leverage": round(summary["avg_leverage"], 2),
                "initial_principal": self.principal,
                "initial_equity": round(init_eq, 2),
                "net_profit": round(net, 4),
                "total_trade_fee": round(summary["fee_total"], 4),
                "total_slippage_cost": round(summary["slip_cost"], 4),
                "total_funding_fee": round(summary["funding_cost"], 6),
                "win_rate_pct": round(float((pnl > 0).mean() * 100), 2),
                "n_trades": n_trades,
                "trading_days": n_days,
                "skipped_opens": summary["skipped_opens"],
                "blowup": summary["blowup"],
                "blowup_time": blowup_time,
            },
            "overfit_filter": {"sharpe_ratio": round(sharpe(ret) * self.ppy**0.5, 4), "deflated_sharpe_pvalue": round(dsr_p, 6), "calmar_ratio": round(calmar(cagr_val, max_dd), 4)},
            "post_cost_survival": {"cvar_95_pct": round(-cvar(ret, 0.05) * 100, 2), "daily_volatility": round(daily_vol, 6), "annual_volatility": round(daily_vol * self.ppy**0.5, 4)},
            "return_quality": {
                "cagr_pct": round(cagr_val * 100, 2),
                "total_return_pct": round(net / init_eq * 100, 2),
                "win_loss_ratio": round(float(abs(wins.mean() / avg_loss)), 4) if len(wins) and avg_loss else None,
                "profit_factor": round(profit_factor(pnl), 4),
                "trimmed_profit": round(trimmed_profit(pnl), 4),
            },
            "live_tolerance": {
                "max_drawdown_pct": round(abs(max_dd) * 100, 2),
                "turnover_rate_annual": round(float((trades["qty"] * trades["exit"]).sum() / nav.mean() * self.ppy / n_days), 4),
                "max_margin_used": round(summary["max_margin_used"], 2),
                "cost_breakeven_multiple": round(max((net + cost) / max(cost, 1e-12), 0.0), 4),
                "stress_2x_cost_profit": round(net - cost, 4),
                "oos_sharpe_change": round(oos_change, 4) if oos_change is not None else None,
            },
        }