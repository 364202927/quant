import math
import operator as op
from bisect import bisect_right
from collections import defaultdict
import numpy as np
import pandas as pd
from server.indicators.baseIndicators import *
from server.utils import switch, switchFn
from server.market import kLong, kShort, kBuy, kSell

"""
结构: 一、统计指标 → 二、评分规则 → 三、事件驱动撮合 → 四、backTest 类
约定:
 - 事件时间 = K线开盘时间,成交价 = 该K线 close(即 K线结束时刻成交)
 - 资金费按 8h(UTC 00/08/16)结算,取结算K线的 open 价,多头付正费率、空头收正费率
 - 保证金采用全仓、不做多空轧差(对冲仓位各自占用保证金,偏保守)
"""

# todo:open_eff,close时添加冲击成本价(基于ADV/参与率/波动率的平方根模型)
# todo:接入参数平原+标准PBO(需同策略多参数日收益矩阵);deflated_sharpe 的 n_trials 改传优化器真实试验次数
# todo:市场类型抽象(MarketConfig): 现货/股票/永续 的手续费、资金费、杠杆、强平、日历
# todo:逐K线(high/low)强平检查与持仓期最大不利波动(MAE)


# ======== 一、统计指标 ========
PPY = 365.0  # 日收益年化周期数(加密货币全年开盘;股票改 252)
def annual_sharpe(returns: np.ndarray, ppy: float = PPY) -> float:
    std = np.std(returns, ddof=1) if len(returns) > 1 else 0.0
    return float(np.mean(returns) / std * math.sqrt(ppy)) if std > 0 else 0.0
def cagr(start: float, end: float, days: int) -> float:
    return (end / start) ** (365.0 / days) - 1.0 if days > 0 and start > 0 and end > 0 else 0.0
def calmar(cagr_val: float, max_dd: float) -> float:# 回撤为 0 且赚钱 → 封顶 999;不赚钱 → 0
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
def deflated_sharpe_pval(returns: np.ndarray, ppy: float = PPY, n_sim: int = 1000,
                         n_trials: int = 100, seed: int = 42):
    """零收益 bootstrap 下 n_trials 个随机策略的最大夏普 ≥ 实测夏普的概率。
    n_trials 应等于真实调参试验次数(目前是经验值,接入优化器后传真实值)"""
    n = len(returns)
    sr_obs = annual_sharpe(returns, ppy)
    if n < 10 or sr_obs == 0.0:
        return 1.0, sr_obs
    rng = np.random.default_rng(seed)
    zero_mean = returns - returns.mean()
    max_sr = np.empty(n_sim)
    for i in range(n_sim):
        batch = zero_mean[rng.integers(0, n, size=(n_trials, n))]
        std = batch.std(axis=1, ddof=1)
        sr = np.divide(batch.mean(axis=1), std, out=np.zeros(n_trials), where=std > 0)
        max_sr[i] = sr.max() * math.sqrt(ppy)
    return float(np.mean(max_sr >= sr_obs)), sr_obs

# ======== 二、评分规则 ========
_GT, _GE, _LT, _LE = op.gt, op.ge, op.lt, op.le
# (指标分区, 指标名, ((比较, 阈值, 得分, 文案), ...) 按序首个命中, 未命中文案)  未命中得 0 分
_RULES = (
    # ---- 盈利 25 ----
    ("return_quality", "total_return_pct",
     ((_GT, 0, 5, "总收益为正"),), "总收益 ≤ 0 (策略未产生正回报)"),
    ("overfit_filter", "sharpe_ratio",
     ((_GT, 1, 10, "夏普 > 1 (风险调整后收益优秀)"), (_GT, 0, 5, "夏普 0~1 (勉强为正)")),
     "夏普 ≤ 0 (风险调整后无超额收益)"),
    ("overfit_filter", "calmar_ratio",
     ((_GT, 1, 10, "卡玛 > 1 (相对回撤收益好)"), (_GT, 0, 5, "卡玛 0~1")),
     "卡玛 ≤ 0 (收益/回撤无吸引力)"),
    # ---- 风险 20 (回撤/CVaR 单位为 %,波动率为小数) ----
    ("live_tolerance", "max_drawdown_pct",
     ((_LT, 10, 8, "最大回撤 < 10%"), (_LT, 20, 4, "最大回撤 10%~20%")),
     "最大回撤 ≥ 20% (实盘压力大)"),
    ("post_cost_survival", "cvar_95_pct",
     ((_LE, 2, 6, "日 CVaR95 ≤ 2% (尾部风险小)"), (_LE, 5, 3, "日 CVaR95 2%~5%")),
     "日 CVaR95 > 5% (极端日亏损大)"),
    ("post_cost_survival", "daily_volatility",
     ((_LT, 0.01, 6, "日波动率 < 1%"), (_LT, 0.03, 3, "日波动率 1%~3%")),
     "日波动率 ≥ 3% (净值起伏过大)"),
    # ---- 过拟合 20 ----
    ("overfit_filter", "deflated_sharpe_pvalue",
     ((_LE, 0.05, 12, "Deflated Sharpe p ≤ 0.05 (非数据窥探)"),),
     "Deflated Sharpe p > 0.05 (高夏普可能是噪声)"),
    ("live_tolerance", "oos_sharpe_change",   # (后半段-前半段)/|前半段|,负=变差
     ((_GE, -0.3, 8, "后半段夏普衰减 < 30% (时间稳定)"), (_GE, -0.5, 4, "后半段夏普衰减 30%~50%")),
     "后半段夏普衰减 > 50% 或无法计算 (前强后弱)"),
    # ---- 稳健 15 ----
    ("return_quality", "profit_factor",
     ((_GE, 1.5, 8, "盈利因子 ≥ 1.5"), (_GE, 1.1, 4, "盈利因子 1.1~1.5")),
     "盈利因子 < 1.1 (盈亏结构薄)"),
    ("return_quality", "trimmed_profit",
     ((_GT, 0, 7, "剔除最赚 5% 交易后仍盈利"),),
     "剔除最赚 5% 交易后亏损 (利润依赖少数极端单)"),
    # ---- 实盘摩擦 20 ----
    ("live_tolerance", "cost_breakeven_multiple",   # 成本放大几倍后利润归零
     ((_GE, 3, 12, "成本放大 ≥ 3 倍才归零 (抗成本恶化)"), (_GE, 2, 6, "成本放大 2~3 倍归零")),
     "成本放大 < 2 倍即归零 (实盘危险)"),
    ("basic", "n_trades",
     ((_GE, 100, 8, "交易数 ≥ 100"), (_GE, 30, 4, "交易数 30~100")),
     "交易数 < 30 (统计置信度低)"),
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
    gate = switch(_VERDICT, basic["status"])      # status=ok 时无对应键 → False
    if gate:
        return {"total_score": 0, "verdict": gate, "details": [gate]}
    total, details = 0, []
    for section, field, tiers, miss in _RULES:
        value = metrics[section][field]
        value = np.nan if value is None else value   # None=无法计算,所有比较为 False → 0 分
        pts, desc = next(((p, d) for cmp, thr, p, d in tiers if cmp(value, thr)), (0, miss))
        total += pts
        details.append(f"{desc} → +{pts}")
    tier = "blowup" if basic["blowup"] else ("discard", "improve", "live")[bisect_right((40, 70), total)]
    return {"total_score": total, "verdict": switch(_VERDICT, tier), "details": details}

# ======== 三、事件驱动撮合 ========
EPS = 1e-8
FUNDING_FREQ = "8h"
LIQUIDATION_RATIO = 0.1     # 账户净值 < 初始权益 * 该比例 → 全部强平
_SIDE = {kLong: 1, kShort: -1}   # 方向 -> 盈亏符号
_KIND = {f"{kLong}:{kBuy}": "open", f"{kLong}:{kSell}": "close",
         f"{kShort}:{kSell}": "open", f"{kShort}:{kBuy}": "close"}
TRADE_COLS = ["traj_id", "side", "open_time", "close_time", "duration", "qty", "entry", "exit",
              "margin", "fee", "pnl", "exit_kind"]

def check_kline(df: pd.DataFrame) -> None:
    """df 以 candle_begin_time(UTC,无时区)为索引。有问题直接抛错并给出首个异常行"""
    bad = df[["open", "close", "funding_bps"]].isna().any(axis=1)
    if bad.any():
        raise ValueError(f"K线含 NaN,首个异常行:\n{df[bad].head(1)}")
    if not (df.index.is_unique and df.index.is_monotonic_increasing):
        raise ValueError("K线时间必须唯一且递增")
    if df.index.tz is not None:
        raise ValueError("raw() 应为 UTC 无时区时间")

def build_events(df: pd.DataFrame, signal: list) -> list:
    """signal -> 全局事件队列。同一时刻先平后开(释放的保证金可立即复用)"""
    times, close = df.index, df["close"].to_numpy()
    events = []
    for tid, traj in enumerate(signal):
        trades = traj["trades"]
        if len(trades) < 2:
            continue
        side, pos = switch(_SIDE, traj["dir"]), [t["pos"] for t in trades]
        if not side or any(b <= a for a, b in zip(pos, pos[1:])):
            raise ValueError(f"轨迹 {tid} 非法: dir={traj['dir']}, pos={pos} (dir 需合法且 pos 严格递增)")
        for t in trades:
            kind = switch(_KIND, f"{traj['dir']}:{t['behavior']}")
            if not kind:
                raise ValueError(f"轨迹 {tid}: behavior={t['behavior']} 与 dir={traj['dir']} 不匹配")
            pct, lv = float(t.get("position%", 10)) / 100.0, float(t.get("lv", 1))
            if not (pct > 0 and lv > 0):     # 同时拦住 NaN
                raise ValueError(f"轨迹 {tid} 的 position%/lv 非法: {t}")
            events.append({"time": times[t["pos"]], "traj_id": tid, "side": side, "kind": kind, "pct": pct,
                           "lv": lv, "price": float(close[t["pos"]]), "last": t is trades[-1]})
    events.sort(key=lambda e: (e["time"], e["kind"] == "open", e["traj_id"]))
    return events

class Account:
    """共享账户。cash=已实现权益(含手续费/资金费),净值=cash+全部持仓浮盈"""

    def __init__(self, equity: float, fee_rate: float, slip: list, liq_ratio: float):
        self.cash, self.fee_rate, self.floor = equity, fee_rate, equity * liq_ratio
        self.slip_lo, self.slip_hi, seed = slip
        self.rng = np.random.default_rng(int(seed))
        self.positions, self.trades = {}, []            # (traj_id, side) -> 持仓
        self.fee_open = self.fee_close = self.slip_cost = self.funding_cost = self.max_margin = 0.0
        self.skipped, self.blown, self.blown_at = 0, False, None

    # ---- 状态 ----
    def used_margin(self) -> float:
        return sum(p["margin"] for p in self.positions.values())
    def nav(self, price: float) -> float:
        return self.cash + sum((price - p["cost"]) * p["qty"] * p["side"] for p in self.positions.values())

    # ---- 事件 ----
    def on_event(self, e: dict) -> None:
        if self.blown:
            return
        switchFn({"open": self._open, "close": self._close}, e["kind"], e=e)
        key = (e["traj_id"], e["side"])
        if e["last"] and key in self.positions:      # 轨迹最后一个事件后仍有残仓 → 按该价强平
            self._exit(key, self.positions[key]["qty"], e["price"], e["time"], "traj_end")
        self._check_liquidation(e["time"], e["price"])

    def _open(self, e: dict) -> None:
        side, slip, nav = e["side"], self.rng.uniform(self.slip_lo, self.slip_hi), self.nav(e["price"])
        margin = min(nav * e["pct"], nav - self.used_margin())   # 不得超过可用保证金
        if margin <= EPS:
            self.skipped += 1
            return
        px = e["price"] * (1 + side * slip)
        qty, fee = margin * e["lv"] / px, margin * e["lv"] * self.fee_rate
        pos = self.positions.setdefault((e["traj_id"], side), {
            "side": side, "traj_id": e["traj_id"], "opened_at": e["time"],
            "qty": 0.0, "cost": 0.0, "margin": 0.0, "fee": 0.0})
        pos["cost"] = (pos["qty"] * pos["cost"] + qty * px) / (pos["qty"] + qty)
        pos["qty"] += qty
        pos["margin"] += margin
        pos["fee"] += fee
        self.cash -= fee
        self.fee_open += fee
        self.slip_cost += qty * px * slip
        self.max_margin = max(self.max_margin, self.used_margin())

    def _close(self, e: dict) -> None:
        pos = self.positions.get((e["traj_id"], e["side"]))
        if pos is None:        # 对应开仓被保证金约束拒绝
            return
        self._exit((e["traj_id"], e["side"]), pos["qty"] * min(e["pct"], 1.0), e["price"], e["time"], "signal")

    def _exit(self, key: tuple, qty: float, price: float, ts, kind: str) -> None:
        pos, side = self.positions[key], key[1]
        frac, slip = qty / pos["qty"], self.rng.uniform(self.slip_lo, self.slip_hi)
        px = price * (1 - side * slip)
        fee_close, fee_open, margin = qty * px * self.fee_rate, pos["fee"] * frac, pos["margin"] * frac
        gross = (px - pos["cost"]) * qty * side
        self.cash += gross - fee_close
        self.fee_close += fee_close
        self.slip_cost += qty * px * slip
        pos["qty"] -= qty
        pos["fee"] -= fee_open
        pos["margin"] -= margin
        self.trades.append({"traj_id": key[0], "side": side, "open_time": pos["opened_at"], "close_time": ts,
                            "duration": int((ts - pos["opened_at"]).total_seconds() // 60), "qty": qty,
                            "entry": pos["cost"], "exit": px, "margin": margin, "fee": fee_open + fee_close,
                            "pnl": gross - fee_open - fee_close, "exit_kind": kind})
        if pos["qty"] <= EPS:
            del self.positions[key]

    def flatten(self, ts, price: float, kind: str) -> None:
        for key in list(self.positions):
            self._exit(key, self.positions[key]["qty"], price, ts, kind)

    def sweep(self, closes: pd.Series) -> None:
        """两个检查点之间逐K线(按 close)检查强平。期间 cash 不变,只需向量化比较浮盈"""
        if self.blown or not self.positions:
            return
        px = closes.to_numpy()
        nav = self.cash + sum(p["qty"] * p["side"] * (px - p["cost"]) for p in self.positions.values())
        hit = np.flatnonzero(nav < self.floor)
        if hit.size:
            self.flatten(closes.index[hit[0]], px[hit[0]], "liquidation")
            self.blown, self.blown_at = True, closes.index[hit[0]]

    def settle_funding(self, ts, price: float, rate: float) -> None:
        if self.blown:
            return
        cost = sum(p["qty"] * price * rate * p["side"] for p in self.positions.values() if p["opened_at"] < ts)
        self.cash -= cost
        self.funding_cost += cost
        self._check_liquidation(ts, price)

    def _check_liquidation(self, ts, price: float) -> None:
        if self.nav(price) < self.floor:
            self.flatten(ts, price, "liquidation")
            self.blown, self.blown_at = True, ts


def run_portfolio(df: pd.DataFrame, events: list, equity: float, fee_rate: float, slip: list):
    """返回 (trades_df, curve_df[time,equity], summary)。curve 含初始点、逐日收盘净值、期末平仓后净值"""
    acct = Account(equity, fee_rate, slip, LIQUIDATION_RATIO)
    close = df["close"]
    # 结算点按时间生成,缺结算K线会在 .loc 处直接 KeyError
    settle_ts = pd.date_range(df.index[0].ceil(FUNDING_FREQ), df.index[-1], freq=FUNDING_FREQ)
    rows = df.loc[settle_ts]
    settle = dict(zip(rows.index, zip(rows["open"], rows["funding_bps"] / 1e4)))
    day_end = set(df.index.to_series().groupby(df.index.normalize()).last())
    by_time = defaultdict(list)
    for e in events:
        by_time[e["time"]].append(e)

    curve, prev = [(df.index[0], equity)], df.index[0]
    for ts in sorted(set(settle) | day_end | set(by_time)):
        acct.sweep(close.loc[prev:ts])
        prev = ts
        if ts in settle:
            acct.settle_funding(ts, *settle[ts])
        for e in by_time.get(ts, ()):
            acct.on_event(e)
        if acct.blown:
            curve.append((acct.blown_at, acct.cash))
            break
        if ts in day_end:
            curve.append((ts, acct.nav(close.at[ts])))
    if not acct.blown:     # 期末仍有持仓 → 按最后一根收盘价平仓(计入手续费/滑点)
        acct.flatten(df.index[-1], close.iloc[-1], "end")
        curve.append((df.index[-1], acct.nav(close.iloc[-1])))

    curve_df = pd.DataFrame(curve, columns=["time", "equity"]).drop_duplicates("time", keep="last")
    lvs = [e["lv"] for e in events if e["kind"] == "open"] or [1.0]
    summary = {"initial_equity": equity, "final_equity": float(curve_df["equity"].iloc[-1]),
               "fee_total": acct.fee_open + acct.fee_close, "slip_cost": acct.slip_cost,
               "funding_cost": acct.funding_cost, "max_margin_used": acct.max_margin,
               "skipped_opens": acct.skipped, "avg_leverage": float(np.mean(lvs)),
               "blowup": acct.blown, "blowup_time": acct.blown_at}
    return pd.DataFrame(acct.trades, columns=TRADE_COLS), curve_df, summary

# ======== 四、回测类 ========
class backTest(baseIndicators):
    "回测数据：性能测试"
    MARGIN_RATIO = 0.95                       # 可用本金占比,保证金不等于100%本金
    DEFAULT_SLIP = (0.0001, 0.0005, 42)       # [slip_min, slip_max, seed]
    MIN_TRADES, MIN_DAYS = 10, 5

    def init(self):
        self.principal = 1000
        self.margin = self.principal * self.MARGIN_RATIO   # 起始权益
        self.fee_rate = 0.0005                             # 单边吃单手续费率
        self.slip = list(self.DEFAULT_SLIP)

    def delimit(self, **kWargs):
        """principal=本金, fee_rate=手续费率, slip=[min,max,seed] (None/缺省项取默认,杠杆由信号 lv 决定,缺省 1)"""
        self.principal = kWargs.get('principal') or self.principal
        self.margin = self.principal * self.MARGIN_RATIO
        self.fee_rate = kWargs.get('fee_rate', self.fee_rate)
        given = list(kWargs.get('slip', self.slip)) + [None] * 3
        self.slip = [d if v is None else v for d, v in zip(self.DEFAULT_SLIP, given)]

    def calculateTa(self, kline, signalPd): pass
    def calculate(self, kLine, signal: list):# raw() 为 UTC0 无时区;回测按 UTC 结算资金费
        df = kLine.raw().set_index("candle_begin_time")
        check_kline(df)
        events = build_events(df, signal)
        trades, curve, summary = run_portfolio(df, events, self.margin, self.fee_rate, self.slip)
        result = self._testing(trades, curve, summary)
        result['score'] = score(result)
        return result

    def _testing(self, trades, curve, summary: dict) -> dict:
        daily = curve.set_index("time")["equity"].resample("D").last().ffill()
        n_trades, n_days = len(trades), len(daily)
        status = "no_trades" if not n_trades else "insufficient_sample" if (
            n_trades < self.MIN_TRADES or n_days < self.MIN_DAYS) else "ok"
        if status != "ok":
            return {"basic": {"status": status, "n_trades": n_trades, "trading_days": n_days},
                    "overfit_filter": {}, "post_cost_survival": {}, "return_quality": {}, "live_tolerance": {}}

        init_eq, final_eq = summary["initial_equity"], summary["final_equity"]
        net = final_eq - init_eq
        nav = np.r_[init_eq, daily.to_numpy()]            # 含初始点,首日损益不丢
        ret = np.diff(nav) / nav[:-1]
        pnl = trades["pnl"].to_numpy()
        max_dd = max_drawdown(nav)
        cagr_val = cagr(init_eq, final_eq, n_days)
        dsr_p, _ = deflated_sharpe_pval(ret)
        daily_vol = float(np.std(ret, ddof=1))

        mid = len(ret) // 2                               # 按时间前/后半段对比夏普
        is_sr, oos_sr = annual_sharpe(ret[:mid]), annual_sharpe(ret[mid:])
        oos_change = (oos_sr - is_sr) / is_sr if is_sr > 0 and len(ret) >= 10 else None   # 前半段无效时稳定性无意义

        # 成本压力:费用+滑点+资金费(仅付出部分)整体放大 k 倍,k=breakeven 时利润归零
        cost = summary["fee_total"] + summary["slip_cost"] + max(summary["funding_cost"], 0.0)
        wins, losses = pnl[pnl > 0], pnl[pnl < 0]
        avg_loss = losses.mean() if len(losses) else 0.0

        return {
            "basic": {
                "status": "ok", "margin": round(final_eq, 2), "leverage": round(summary["avg_leverage"], 2),
                "initial_principal": self.principal, "initial_equity": round(init_eq, 2),
                "net_profit": round(net, 4), "total_trade_fee": round(summary["fee_total"], 4),
                "total_slippage_cost": round(summary["slip_cost"], 4),
                "total_funding_fee": round(summary["funding_cost"], 6),
                "win_rate_pct": round(float((pnl > 0).mean() * 100), 2), "n_trades": n_trades,
                "trading_days": n_days, "skipped_opens": summary["skipped_opens"],
                "blowup": summary["blowup"]},
            "overfit_filter": {
                "sharpe_ratio": round(annual_sharpe(ret), 4), "deflated_sharpe_pvalue": round(dsr_p, 6),
                "calmar_ratio": round(calmar(cagr_val, max_dd), 4)},
            "post_cost_survival": {
                "cvar_95_pct": round(-cvar(ret, 0.05) * 100, 2), "daily_volatility": round(daily_vol, 6),
                "annual_volatility": round(daily_vol * PPY ** 0.5, 4)},
            "return_quality": {
                "cagr_pct": round(cagr_val * 100, 2), "total_return_pct": round(net / init_eq * 100, 2),
                "win_loss_ratio": round(float(abs(wins.mean() / avg_loss)), 4) if len(wins) and avg_loss else None,
                "profit_factor": round(profit_factor(pnl), 4),
                "trimmed_profit": round(trimmed_profit(pnl), 4)},
            "live_tolerance": {
                "max_drawdown_pct": round(abs(max_dd) * 100, 2),
                "turnover_rate_annual": round(float((trades["qty"] * trades["exit"]).sum() / nav.mean() * PPY / n_days), 4),
                "max_margin_used": round(summary["max_margin_used"], 2),
                "cost_breakeven_multiple": round(max((net + cost) / max(cost, 1e-12), 0.0), 4),
                "stress_2x_cost_profit": round(net - cost, 4),
                "oos_sharpe_change": round(oos_change, 4) if oos_change is not None else None},
        }