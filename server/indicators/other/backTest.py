from server.indicators.baseIndicators import *
from server.market.consts import kLong,kShort,kBuy,kSell
from typing import NamedTuple
# todo:open_eff,close时添加冲击成本价,模拟资金量大的情况下对市场的影响
# todo:当前只实现了单条交易估计,多条交易轨迹相交没做
# todo:后面添加type 对现货,股票,永续合约的回测

Year = 365  # 每一年有几天开盘，若是股票252天


# ---- score 评分辅助函数（纯函数，避免每次调用重建） ----
def _skewness(x: np.ndarray) -> float:
    n = len(x)
    if n < 3:
        return 0.0
    mean_x = np.mean(x)
    std_x = np.std(x, ddof=1)
    if std_x == 0:
        return 0.0
    m3 = np.sum((x - mean_x) ** 3) / n
    return (n * n) / ((n - 1) * (n - 2)) * m3 / (std_x ** 3)

def _kurtosis(x: np.ndarray) -> float:
    n = len(x)
    if n < 4:
        return 0.0
    mean_x = np.mean(x)
    std_x = np.std(x, ddof=1)
    if std_x == 0:
        return 0.0
    m4 = np.sum((x - mean_x) ** 4) / n
    k = (n * (n + 1)) / ((n - 1) * (n - 2) * (n - 3)) * m4 / (std_x ** 4)
    k -= 3.0 * (n - 1) * (n - 1) / ((n - 2) * (n - 3))
    return k

def _annual_sharpe(returns: np.ndarray, ppy: float) -> float:
    std_r = np.std(returns, ddof=1)
    if std_r == 0:
        return 0.0
    return np.mean(returns) / std_r * math.sqrt(ppy)

def _sortino_ratio(returns: np.ndarray, ppy: float) -> float:
    downside = returns[returns < 0]
    if len(downside) == 0:
        return 999.0
    downside_std = np.std(downside, ddof=1)
    if downside_std == 0:
        return 0.0
    return math.sqrt(ppy) * np.mean(returns) / downside_std

def _cagr(start: float, end: float, days: int) -> float:
    if days <= 0 or start <= 0:
        return 0.0
    years = days / 365.0
    return (end / start) ** (1.0 / years) - 1.0

def _calmar_ratio(cagr_val: float, max_dd: float) -> float:
    if max_dd == 0:
        return 0.0
    return cagr_val / abs(max_dd)

def _cvar(returns: np.ndarray, alpha: float) -> float:
    cutoff = np.percentile(returns, alpha * 100)
    tail = returns[returns <= cutoff]
    if len(tail) == 0:
        return 0.0
    return float(tail.mean())

def _max_drawdown(equity: np.ndarray, close_times: np.ndarray):
    running_max = np.maximum.accumulate(equity)
    drawdowns = (equity - running_max) / running_max
    max_dd = float(drawdowns.min())
    trough_idx = int(drawdowns.argmin())
    peak_vals = np.where(np.isclose(equity[:trough_idx + 1], running_max[trough_idx]))[0]
    peak_idx = int(peak_vals[-1]) if len(peak_vals) > 0 else trough_idx
    dd_duration = trough_idx - peak_idx
    recovery_days = None
    peak_value = running_max[trough_idx]
    remaining = equity[trough_idx + 1:]
    recovered = np.where(remaining >= peak_value)[0]
    if len(recovered) > 0:
        ri = trough_idx + 1 + recovered[0]
        recovery_days = int((close_times[ri] - close_times[trough_idx]).days)
    return max_dd, dd_duration, recovery_days, drawdowns

def _deflated_sharpe_pval(returns: np.ndarray, ppy: float,
                           n_simulations: int = 1000,
                           block_size: int | None = None,
                           seed: int = 42):
    """块状 bootstrap 通货紧缩夏普检验（内层循环已向量化）"""
    n = len(returns)
    sr_obs = _annual_sharpe(returns, ppy)
    if n < 10 or sr_obs == 0.0:
        return 1.0, sr_obs

    rng = np.random.default_rng(seed)
    if block_size is None:
        block_size = max(2, int(np.sqrt(n)))

    simulated_max_sr = np.zeros(n_simulations)
    n_strategies = 100
    sqrt_ppy = np.sqrt(ppy)
    for i in range(n_simulations):
        n_blocks = (n + block_size - 1) // block_size
        starts = rng.integers(0, n - block_size + 1, size=n_blocks)
        blocks = [returns[s:s + block_size] for s in starts]
        sim_zero = np.concatenate(blocks)[:n]
        sim_zero = sim_zero - np.mean(sim_zero)

        # 向量化：一次生成所有策略的随机索引矩阵
        idx_matrix = rng.integers(0, n, size=(n_strategies, n))
        ret_batch = sim_zero[idx_matrix]
        means = ret_batch.mean(axis=1)
        stds = ret_batch.std(axis=1, ddof=1)
        mask = stds > 0
        sharpes = np.where(mask, means / stds * sqrt_ppy, 0.0)
        simulated_max_sr[i] = sharpes.max()

    p_value = float(np.mean(simulated_max_sr >= sr_obs))
    return p_value, sr_obs

def _consecutive_streaks(returns: np.ndarray):
    if len(returns) == 0:
        return 0, 0
    signs = np.sign(returns)
    changes = np.where(np.diff(signs) != 0)[0] + 1
    groups = np.split(signs, changes)
    max_wins = max((len(g) for g in groups if len(g) > 0 and g[0] > 0), default=0)
    max_losses = max((len(g) for g in groups if len(g) > 0 and g[0] <= 0), default=0)
    return max_wins, max_losses

def _rolling_sharpe_metrics(returns: np.ndarray, window: int | None = None):
    if window is None:
        window = max(len(returns) // 5, 5)
    if len(returns) < window:
        return 0.0, 0.0
    s = pd.Series(returns)
    rolling_mean = s.rolling(window).mean()
    rolling_std = s.rolling(window).std(ddof=1)
    rolling_sr = (rolling_mean / rolling_std).dropna().replace([np.inf, -np.inf], 0.0).fillna(0.0)
    return float(rolling_sr.std(ddof=1)), float(rolling_sr.min())


class backTest(baseIndicators):
    "回测数据：性能测试"
    level = 1  # 杠杆
    principal = 0  # 本金
    margin = 0     #保证金

    def init(self):
        self.principal = 1000
        self.margin = self.principal
        self.level = 1

    def delimit(self, **kWargs):
        if kWargs.get('principal'):
            self.principal = kWargs['principal']
            self.margin = self.principal * 0.95  #保证金不等于100%本金
        # if kWargs.get('margin'): self.margin = kWargs['margin']
        if kWargs.get('lv'):
            self.level = kWargs['lv']

    def calculateTa(self, kline:pdData, signalPd:pd.DataFrame):pass
    def calculate(self, kLine: pdData, signal: list):
        # 1.将信号转换成订单
        orders = self._transform2data(kLine, signal)
        # logFormat(orders)
        # 2.对每笔订单计算利润
        statistical = self._equityCurve(orders)
        # print(statistical.get())
        # 3.计算策划关键的回测值
        result = self.score(statistical)
        # logJson(result)
        return result

    def _transform2data(self, kLine: pdData, signal: list) -> list:
        # def _transform2data(self, kLine: pdData, signalPd: list) -> list:
        df = kLine.get()
        rows = []
        for traj in signal:
            trades = traj.get("trades", [])
            if len(trades) < 2:
                continue
            enriched = []
            for t in trades:
                kr = df.loc[t["pos"]]
                enriched.append({**t,
                                "time": kr["candle_begin_time"],
                                "price": float(kr["close"])})
            first_time = enriched[0]["time"]
            for e in enriched:
                e["duration"] = int((e["time"] - first_time).total_seconds() // 60)
            # 轨迹方向: "LONG" 或 "SHORT"，第一个动作的 behavior 决定了开仓方向
            rows.append({"dir": traj["dir"],
                        "trades": enriched})
        return rows

    def _equityCurve(self, orders: list) -> pdData:
        # ---- 回测费率与阈值（局部常量，便于敏感性分析） ----
        TAKER_FEE_RATE = 0.0005          # 单边吃单手续费率
        FUNDING_RATE_8H = 0.0001         # 单次 8h 资金费率
        FUNDING_INTERVAL = '8h'
        SLIP_MIN, SLIP_MAX = 0.0001, 0.0005
        LIQUIDATION_RATIO = 0.1          # 剩余保证金 < 本金 * 该比例 视为爆仓
        QTY_EPSILON = 1e-8               # 持仓残量阈值
        DEFAULT_UTILIZATION = 0.1        # 单笔默认仓位占比
        DIR_MAP = {kLong: (kBuy, 1), kShort: (kSell, -1)} # 方向 → (增仓行为, 盈亏符号)
        class trajResult(NamedTuple):
            profit: float
            fee: float
            rate: float
            margin_used: float
            avg_slip_pct: float
            funding_fee: float
            total_notional: float
        columns = ["dir", "openTime", "duration", "openPrice", "closePrice", "lv",
                   "fee", "profit_Usdt", "rate", "slip", "margin_after", "funding_fee",
                   "total_notional"]
        def _funding_count(open_time, close_time) -> int:# 持仓期内覆盖的 8h 结算点次数
            ticks = pd.date_range(start=open_time.floor('D'), end=close_time.ceil('D'),freq=FUNDING_INTERVAL)
            return int(((ticks > open_time) & (ticks <= close_time)).sum())
        def _close(qty: float, eff_price: float, avg_cost: float, sign: int):# 平仓 qty 张：返回 (手续费, 已实现盈亏)
            fee = qty * eff_price * TAKER_FEE_RATE
            profit = (eff_price - avg_cost) * qty * sign
            return fee, profit
        def _row(meta: dict, *, fee=0.0, profit=0.0, rate=0.0, slip=0.0, funding_fee=0.0,
                 total_notional=0.0) -> dict: #返回值
            return {**meta, "fee": fee, "profit_Usdt": profit, "rate": rate, "slip": slip,
                    "margin_after": self.margin, "funding_fee": funding_fee,
                    "total_notional": total_notional}

        def _process_trajectory(trades: list, dir: str, equity: float) -> trajResult:
            add_behavior, sign = DIR_MAP[dir]
            qty = avg_cost = fee_total = realized_profit = 0.0
            max_notional = used_margin_total = total_notional = 0.0
            slip_sum, slip_count = 0.0, 0
            last_idx = len(trades) - 1

            for i, t in enumerate(trades):
                pct = (t['position%'] / 100.0) if pd.notna(t.get('position%')) else DEFAULT_UTILIZATION
                price, lv = t["price"], t["lv"]
                is_increase = (t["behavior"] == add_behavior)

                # 滑点：每个动作独立生成，开仓/平仓方向对称不利
                slip = random.uniform(SLIP_MIN, SLIP_MAX)
                slip_sum += slip
                slip_count += 1
                eff_price = price * (1 + sign * slip) if is_increase else price * (1 - sign * slip)

                if is_increase:
                    margin_used = equity * pct
                    d_qty = margin_used * lv / eff_price
                    if d_qty <= 0:
                        continue
                    fee_total += d_qty * eff_price * TAKER_FEE_RATE
                    avg_cost = eff_price if qty == 0 else (qty * avg_cost + d_qty * eff_price) / (qty + d_qty)
                    qty += d_qty
                    used_margin_total += margin_used
                else:
                    close_qty = qty if i == last_idx else qty * pct
                    if close_qty <= 0:
                        continue
                    fee, profit = _close(close_qty, eff_price, avg_cost, sign)
                    fee_total += fee
                    realized_profit += profit
                    qty -= close_qty
                    if qty <= QTY_EPSILON:
                        qty = avg_cost = 0.0
                    # 注意：保证金未释放，rate 计算基于累计 used_margin_total

                trade_notional = d_qty * eff_price if is_increase else close_qty * eff_price
                total_notional += trade_notional
                max_notional = max(max_notional, qty * eff_price)

            # 残留仓位强制平仓
            if qty > QTY_EPSILON:
                slip = random.uniform(SLIP_MIN, SLIP_MAX)
                slip_sum += slip
                slip_count += 1
                eff_price = trades[-1]["price"] * (1 - sign * slip)
                fee, profit = _close(qty, eff_price, avg_cost, sign)
                fee_total += fee
                realized_profit += profit
                total_notional += qty * eff_price
                qty = 0.0

            fee_funding = _funding_count(trades[0]["time"], trades[-1]["time"]) * max_notional * FUNDING_RATE_8H
            fee_total = round(fee_total + fee_funding, 6)
            profit_usdt = round(realized_profit - fee_total, 4)
            rate = round(profit_usdt / used_margin_total * 100, 2) if used_margin_total else 0.0
            avg_slip_pct = (round(slip_sum / slip_count, 6) * 100) if slip_count else 0.0
            return trajResult(profit_usdt, fee_total, rate, used_margin_total, avg_slip_pct, fee_funding, total_notional)
        #logic
        rows, blowup = [], False
        for order in orders:
            first, last = order["trades"][0], order["trades"][-1]
            meta = {"dir": order["dir"], "openTime": first["time"], "duration": last["duration"],
                    "openPrice": first["price"], "closePrice": last["price"], "lv": first["lv"]}

            if blowup:
                rows.append(_row(meta))
                continue

            r = _process_trajectory(order["trades"], order["dir"], self.margin)
            self.margin += r.profit
            if self.margin < self.principal * LIQUIDATION_RATIO:
                print("爆仓了")
                blowup = True

            rows.append(_row(meta, fee=r.fee, profit=r.profit, rate=r.rate,
                             slip=r.avg_slip_pct, funding_fee=r.funding_fee,
                             total_notional=r.total_notional))

        # 计算平均杠杆
        lvs = [o["trades"][0]["lv"] for o in orders]
        self.level = sum(lvs) / len(lvs) if lvs else self.level

        # 一次性构造 DataFrame，避免逐行 pd.concat 的 O(N²) 开销
        return pdData(columns, style='xml', data=rows)
    
    def score(self, statistical: pdData) -> dict:
        df = statistical.get().copy()
        n_trades = len(df)
        if n_trades == 0:
            return {
                "basic": {"status": "no_trades"},
                "overfit_filter": {}, "post_cost_survival": {}, "return_quality": {}, "live_tolerance": {}
            }

        # ---------- derived columns ----------
        if "margin_after" not in df.columns:
            df["margin_after"] = self.principal * 0.95 + df["profit_Usdt"].cumsum()

        df["margin_before"] = df["margin_after"].shift(1)
        df.loc[df.index[0], "margin_before"] = df["margin_after"].iloc[0] - df["profit_Usdt"].iloc[0]

        df["trade_return"] = np.where(
            df["margin_before"] > 0,
            df["profit_Usdt"] / df["margin_before"],
            0.0
        )
        close_times = df["openTime"] + pd.to_timedelta(df["duration"], unit="min")
        df["closeTime"] = close_times
        total_days = max((close_times.max() - df["openTime"].min()).days, 1)
        trade_return = df["trade_return"].values
        profit_series = df["profit_Usdt"].values
        margin_curve = df["margin_after"].values
        periods_per_year = n_trades / (total_days / 365.0) if total_days > 0 else n_trades

        # ---------- basic ----------
        final_margin = float(df["margin_after"].iloc[-1])
        net_profit = float(profit_series.sum())
        total_funding = float(df["funding_fee"].sum()) if "funding_fee" in df.columns else 0.0
        total_trade_fee = float(df["fee"].sum()) - total_funding
        win_rate = float((profit_series > 0).sum() / n_trades * 100)

        basic = {
            "margin": round(final_margin, 2),
            "leverage": self.level,
            "initial_principal": self.principal,
            "remaining_capital": round(self.principal + net_profit, 2),
            "net_profit": round(net_profit, 4),
            "total_trade_fee": round(total_trade_fee, 4),
            "total_funding_fee": round(total_funding, 8),
            "win_rate_pct": round(win_rate, 2),
            "n_trades": n_trades,
            "trading_days": total_days,
        }

        # ---------- overfit filter ----------
        sr = _annual_sharpe(trade_return, periods_per_year)
        dsr_pval, dsr_val = _deflated_sharpe_pval(trade_return, periods_per_year)
        cagr_val = _cagr(float(df["margin_before"].iloc[0]), float(df["margin_after"].iloc[-1]), total_days)
        max_dd_val, dd_dur, recovery_days, _ = _max_drawdown(margin_curve, close_times.values)
        calmar = _calmar_ratio(cagr_val, max_dd_val)
        sortino = _sortino_ratio(trade_return, periods_per_year)

        overfit = {
            "sharpe_ratio": round(sr, 4),
            "deflated_sharpe": round(dsr_val, 4),
            "deflated_sharpe_pvalue": round(dsr_pval, 6),
            "calmar_ratio": round(calmar, 4),
            "sortino_ratio": round(sortino, 4),
        }

        # ---------- post-cost survival ----------
        cvar_95 = _cvar(trade_return, 0.05)
        cvar_99 = _cvar(trade_return, 0.01)

        # 完整的每日净值序列（含无交易日填前值），避免低估隔夜波动
        close_date = close_times.dt.date
        daily_margin_last = df.groupby(close_date)["margin_after"].last()
        full_dates = pd.date_range(start=daily_margin_last.index.min(),
                                   end=daily_margin_last.index.max(), freq="D")
        daily_nav = daily_margin_last.reindex(full_dates.date, method="ffill")
        daily_ret = daily_nav.pct_change().dropna()
        daily_vol = float(np.std(daily_ret, ddof=1)) if len(daily_ret) > 1 else 0.0
        annual_vol = daily_vol * math.sqrt(365)
        vol_deviation = abs(annual_vol - 0.20) / 0.20 * 100 if annual_vol > 0 else None

        survival = {
            "cvar_95_pct": round(-cvar_95 * 100, 2),
            "cvar_99_pct": round(-cvar_99 * 100, 2),
            "daily_volatility": round(daily_vol, 6),
            "annual_volatility": round(annual_vol, 4),
            "target_volatility": 0.20,
            "volatility_deviation_pct": round(vol_deviation, 2) if vol_deviation is not None else "N/A",
        }

        # ---------- return quality ----------
        wins = df[df["profit_Usdt"] > 0]
        losses = df[df["profit_Usdt"] < 0]
        n_wins, n_losses = len(wins), len(losses)
        total_win = float(wins["profit_Usdt"].sum()) if n_wins > 0 else 0.0
        total_loss = float(losses["profit_Usdt"].sum()) if n_losses > 0 else 0.0

        monthly = df.groupby(close_times.dt.to_period("M"))["profit_Usdt"].sum()
        month_win_rate = float((monthly > 0).sum() / len(monthly) * 100) if len(monthly) > 0 else 0.0

        weekly = df.groupby(close_times.dt.to_period("W"))["profit_Usdt"].sum()
        week_win_rate = float((weekly > 0).sum() / len(weekly) * 100) if len(weekly) > 0 else 0.0

        total_return_pct = float(
            (df["margin_after"].iloc[-1] - df["margin_before"].iloc[0])
            / df["margin_before"].iloc[0] * 100
        )

        # win_loss_ratio = 平均单笔盈利 / |平均单笔亏损|（盈亏比）
        # profit_factor = 总盈利 / |总亏损|（盈利因子）
        avg_win = total_win / n_wins if n_wins > 0 else 0.0
        avg_loss = total_loss / n_losses if n_losses > 0 else 0.0

        quality = {
            "win_count": n_wins,
            "loss_count": n_losses,
            "total_win_amount": round(total_win, 4),
            "total_loss_amount": round(total_loss, 4),
            "max_single_win": round(float(wins["profit_Usdt"].max()), 4) if n_wins > 0 else 0.0,
            "max_single_loss": round(float(losses["profit_Usdt"].min()), 4) if n_losses > 0 else 0.0,
            "cagr_pct": round(cagr_val * 100, 2),
            "total_return_pct": round(total_return_pct, 2),
            "win_loss_ratio": round(abs(avg_win / avg_loss), 4) if avg_loss != 0 else None,
            "profit_factor": round(abs(total_win / total_loss), 4) if total_loss != 0 else None,
            "return_skewness": round(_skewness(trade_return), 4),
            "return_kurtosis": round(_kurtosis(trade_return), 4),
            "monthly_win_rate_pct": round(month_win_rate, 2),
            "weekly_win_rate_pct": round(week_win_rate, 2),
        }

        # ---------- turnover & capacity ----------
        total_notional = float(df["total_notional"].sum()) if "total_notional" in df.columns else 0.0
        avg_margin = float(np.mean(margin_curve)) if len(margin_curve) > 0 else final_margin
        turnover_rate = (total_notional / avg_margin * (365.0 / total_days)) if avg_margin > 0 else 0.0
        capacity_estimate = avg_margin / max(turnover_rate, 0.01) if turnover_rate > 0 else None

        # ---------- live tolerance ----------
        max_wins, max_losses = _consecutive_streaks(trade_return)
        roll_sr_std, roll_sr_min = _rolling_sharpe_metrics(trade_return)
        extra_cost = (df["slip"].values / 100.0) * df["margin_before"].values * df["lv"].values
        stressed_profit = float(profit_series.sum() - extra_cost.sum())

        # OOS: 样本内/外夏普衰减率
        mid = n_trades // 2
        if mid >= 5:
            is_ret = trade_return[:mid]
            oos_ret = trade_return[mid:]
            is_ppy = mid / max(total_days / 2.0 / 365.0, 0.01)
            oos_ppy = (n_trades - mid) / max(total_days / 2.0 / 365.0, 0.01)
            is_sr = _annual_sharpe(is_ret, is_ppy)
            oos_sr = _annual_sharpe(oos_ret, oos_ppy)
            oos_decay = (is_sr - oos_sr) / is_sr if is_sr != 0 else None
        else:
            oos_decay = None

        stress = {
            "max_drawdown_pct": round(abs(max_dd_val) * 100, 2),
            "max_drawdown": round(max_dd_val, 4),
            "drawdown_duration_trades": dd_dur,
            "recovery_days": recovery_days,
            "turnover_rate_annual": round(turnover_rate, 4),
            "capacity_estimate": round(capacity_estimate, 2) if capacity_estimate is not None else None,
            "stress_2x_slip_profit": round(stressed_profit, 4),
            "stress_original_profit": round(net_profit, 4),
            "rolling_sharpe_std": round(roll_sr_std, 4),
            "rolling_sharpe_min": round(roll_sr_min, 4),
            "max_consecutive_wins": max_wins,
            "max_consecutive_losses": max_losses,
            "oos_sharpe_decay": round(oos_decay, 4) if oos_decay is not None else None,
        }

        return {
            "basic": basic,
            "overfit_filter": overfit,
            "post_cost_survival": survival,
            "return_quality": quality,
            "live_tolerance": stress,
        }
    
    #概率过拟合 (Probability of Backtest Overfitting) 的 CSCV 实现,需要同策略异参数
    def pbo_cscv(strategies_returns: list, n_blocks: int = 10,seed: int = 42) -> float:
        if len(strategies_returns) < 2:
            raise ValueError("PBO 至少需要 2 个策略来比较排名")
        n_strategies = len(strategies_returns)
        n = len(strategies_returns[0])
        if n % n_blocks != 0:
            # 简单截断到整除长度
            valid_len = (n // n_blocks) * n_blocks
            strategies_returns = [sr[:valid_len] for sr in strategies_returns]
            n = valid_len

        block_len = n // n_blocks
        # 将每个策略的收益率转换为块和（或块夏普），这里用块内总收益率（或平均收益率）
        block_returns = np.zeros((n_strategies, n_blocks))
        for i, sr in enumerate(strategies_returns):
            for b in range(n_blocks):
                start = b * block_len
                end = start + block_len
                block_returns[i, b] = np.mean(sr[start:end])  # 块内平均收益，也可用夏普
        
        # 样本内块数为总块数的一半
        n_is = n_blocks // 2
        # 组合对称：枚举所有可能的样本内组合
        from itertools import combinations
        all_combos = list(combinations(range(n_blocks), n_is))
        n_combos = len(all_combos)
        
        # 记录每个组合的样本内最优策略在样本外的相对排名
        oos_ranks = np.zeros(n_combos)
        
        for c, is_blocks in enumerate(all_combos):
            oos_blocks = [b for b in range(n_blocks) if b not in is_blocks]
            # 样本内、外平均收益（或夏普）矩阵
            is_avg = np.mean(block_returns[:, is_blocks], axis=1)  # (n_strategies,)
            oos_avg = np.mean(block_returns[:, oos_blocks], axis=1)
            
            # 样本内最佳策略的索引
            best_is_idx = np.argmax(is_avg)
            # 该策略在样本外的排名（从大到小，1 为最优）
            # 归一化排名 w̅ ∈ [0, 1]，0 表示最差，1 表示最优
            order = np.argsort(oos_avg)   # 升序
            rank = np.where(order == best_is_idx)[0][0] / (n_strategies - 1) if n_strategies > 1 else 0.5
            oos_ranks[c] = rank
        
        # PBO = 样本内最优落在样本外后 50%（排名 < 0.5）的比例
        pbo = np.mean(oos_ranks < 0.5)
        return float(pbo)