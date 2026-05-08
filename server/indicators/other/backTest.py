from server.indicators.baseIndicators import *
from server.market.consts import kLong,kShort,kBuy,kSell
from typing import NamedTuple
# open_eff,close时添加冲击成本价,模拟资金量大的情况下对市场的影响

# todo:改版添加指标
# 1.当前的币和收益做一个总收益率
# 2.月度表现
# 3.风险等级评分
# 4.最大回撤，日，周，历史
Year = 365  # 每一年有几天开盘，若是股票252天


class _TrajResult(NamedTuple):
    profit: float
    fee: float
    rate: float
    margin_used: float
    avg_slip_pct: float
    funding_fee: float

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
        logFormat(orders)
        # 2.对每笔订单计算利润
        statistical = self._equityCurve(orders)
        print(statistical.get())
        # 3.评分
        result = self.score(statistical)
        logJson(result)

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
        columns = ["dir", "openTime", "duration", "openPrice", "closePrice", "lv",
                   "fee", "profit_Usdt", "rate", "slip", "margin_after", "funding_fee"]
        def _funding_count(open_time, close_time) -> int:# 持仓期内覆盖的 8h 结算点次数
            ticks = pd.date_range(start=open_time.floor('D'), end=close_time.ceil('D'),freq=FUNDING_INTERVAL)
            return int(((ticks > open_time) & (ticks <= close_time)).sum())

        def _close(qty: float, eff_price: float, avg_cost: float, sign: int):# 平仓 qty 张：返回 (手续费, 已实现盈亏)
            fee = qty * eff_price * TAKER_FEE_RATE
            profit = (eff_price - avg_cost) * qty * sign
            return fee, profit

        def _process_trajectory(trades: list, dir: str, equity: float) -> trajResult:
            try:
                add_behavior, sign = DIR_MAP[dir]
            except KeyError as e:
                raise ValueError(f"Unknown dir: {dir}") from e

            qty = avg_cost = fee_total = realized_profit = 0.0
            max_notional = used_margin_total = 0.0
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
                qty = 0.0

            fee_funding = _funding_count(trades[0]["time"], trades[-1]["time"]) * max_notional * FUNDING_RATE_8H
            fee_total = round(fee_total + fee_funding, 6)
            profit_usdt = round(realized_profit - fee_total, 4)
            rate = round(profit_usdt / used_margin_total * 100, 2) if used_margin_total else 0.0
            avg_slip_pct = (round(slip_sum / slip_count, 6) * 100) if slip_count else 0.0
            return trajResult(profit_usdt, fee_total, rate, used_margin_total, avg_slip_pct, fee_funding)

        def _row(meta: dict, *, fee=0.0, profit=0.0, rate=0.0, slip=0.0, funding_fee=0.0) -> dict:
            return {**meta, "fee": fee, "profit_Usdt": profit, "rate": rate,
                    "slip": slip, "margin_after": self.margin, "funding_fee": funding_fee}

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
                             slip=r.avg_slip_pct, funding_fee=r.funding_fee))

        # 一次性构造 DataFrame，避免逐行 pd.concat 的 O(N²) 开销
        return pdData(columns, style='xml', data=rows)
    
    def score(self, statistical: pdData) -> dict:
        df = statistical.get()
        n_trades = len(df)
        if n_trades == 0:
            return {
                "基础数据": {"状态": "无交易记录"},
                "过拟合过滤": {}, "成本后生存": {}, "收益属性质量": {}, "实盘耐受力": {}
            }

        # ---------- 衍生列 ----------
        if "margin_after" not in df.columns:
            df["margin_after"] = self.principal * 0.95 + df["profit_Usdt"].cumsum()

        df["margin_before"] = df["margin_after"].shift(1)
        df.loc[df.index[0], "margin_before"] = df["margin_after"].iloc[0] - df["profit_Usdt"].iloc[0]

        df["trade_return"] = np.where(
            df["margin_before"] > 0,
            df["profit_Usdt"] / df["margin_before"],
            0.0
        )
        df["closeTime"] = df["openTime"] + pd.to_timedelta(df["duration"], unit="min")
        total_days = max((df["closeTime"].max() - df["openTime"].min()).days, 1)
        trade_return = df["trade_return"].values
        profit_series = df["profit_Usdt"].values
        margin_curve = df["margin_after"].values
        periods_per_year = n_trades / (total_days / 365.0) if total_days > 0 else n_trades

        # ---------- 内部函数 ----------
        def _norm_cdf(x: float) -> float:
            return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

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

        def _max_drawdown(equity: np.ndarray):
            running_max = np.maximum.accumulate(equity)
            drawdowns = (equity - running_max) / running_max
            max_dd = float(drawdowns.min())
            trough_idx = int(drawdowns.argmin())
            peak_vals = np.where(equity[:trough_idx + 1] == running_max[trough_idx])[0]
            peak_idx = int(peak_vals[-1]) if len(peak_vals) > 0 else trough_idx
            dd_duration = trough_idx - peak_idx
            recovery_days = None
            peak_value = running_max[trough_idx]
            for i in range(trough_idx + 1, len(equity)):
                if equity[i] >= peak_value:
                    recovery_days = int((df["closeTime"].iloc[i] - df["closeTime"].iloc[trough_idx]).days)
                    break
            return max_dd, dd_duration, recovery_days, drawdowns

        def _deflated_sharpe_pval(returns: np.ndarray, ppy: float):
            sr = _annual_sharpe(returns, ppy)
            T = len(returns)
            if T < 3:
                return 1.0, sr
            skew = _skewness(returns)
            kurt = _kurtosis(returns)  # 超额峰度 (excess kurtosis)
            SR_star = 0.0
            # PSR 分母: sqrt(1 - γ3·SR + (γ4-1)/4 · SR²)
            # γ4 = kurt + 3, 故 γ4-1 = kurt + 2
            inner = 1.0 - skew * sr + (kurt + 2.0) / 4.0 * sr ** 2
            if inner <= 0:
                inner = 1.0  # 非正态修正失效时回退到正态假设
            z_score = (sr - SR_star) * math.sqrt(T - 1) / math.sqrt(inner)
            p_value = 1.0 - _norm_cdf(z_score)
            return p_value, sr

        def _pbo_sharpe_stability(returns: np.ndarray) -> dict:
            n = len(returns)
            mid = n // 2
            if mid < 2:
                return {"SR_first_half": None, "SR_second_half": None,
                        "SR_ratio": None, "PBO_flag": "样本不足"}
            r1, r2 = returns[:mid], returns[mid:]
            std1, std2 = np.std(r1, ddof=1), np.std(r2, ddof=1)
            sr1 = float(np.mean(r1) / std1) if std1 > 0 else 0.0
            sr2 = float(np.mean(r2) / std2) if std2 > 0 else 0.0
            sr_ratio = sr2 / sr1 if sr1 != 0 else None
            if sr_ratio is None:
                flag = "无法判定"
            elif sr_ratio < 0:
                flag = "严重衰减"
            elif sr_ratio < 0.5:
                flag = "衰减"
            else:
                flag = "稳定"
            return {"SR_first_half": sr1, "SR_second_half": sr2,
                    "SR_ratio": sr_ratio, "PBO_flag": flag}

        def _consecutive_streaks(returns: np.ndarray):
            max_wins, max_losses = 0, 0
            cur_wins, cur_losses = 0, 0
            for r in returns:
                if r > 0:
                    cur_wins += 1
                    cur_losses = 0
                    max_wins = max(max_wins, cur_wins)
                else:
                    cur_losses += 1
                    cur_wins = 0
                    max_losses = max(max_losses, cur_losses)
            return max_wins, max_losses

        def _rolling_sharpe_std(returns: np.ndarray, window: int = None) -> float:
            if window is None:
                window = max(len(returns) // 5, 5)
            if len(returns) < window:
                return 0.0
            rolling = []
            for i in range(len(returns) - window + 1):
                seg = returns[i:i + window]
                seg_std = np.std(seg, ddof=1)
                rolling.append(float(np.mean(seg) / seg_std) if seg_std > 0 else 0.0)
            return float(np.std(rolling, ddof=1))

        def _cost_stress_test(d: pd.DataFrame, multiplier: float = 2.0) -> float:
            extra_cost = (multiplier - 1.0) * (d["slip"] / 100.0) * d["margin_before"] * d["lv"]
            return float(d["profit_Usdt"].sum() - extra_cost.sum())

        # ---------- 基础数据 ----------
        final_margin = float(df["margin_after"].iloc[-1])
        net_profit = float(profit_series.sum())
        total_funding = float(df["funding_fee"].sum()) if "funding_fee" in df.columns else 0.0
        total_trade_fee = float(df["fee"].sum()) - total_funding
        win_rate = float((profit_series > 0).sum() / n_trades * 100)

        basic = {
            "保证金": round(final_margin, 2),
            "杠杆": self.level,
            "初始本金": self.principal,
            "剩余资金": round(self.principal + net_profit, 2),
            "净利润": round(net_profit, 4),
            "总手续费": round(total_trade_fee, 4),
            "总资金费率": round(total_funding, 8),
            "胜率": round(win_rate, 2),
            "交易笔数": n_trades,
            "交易天数": total_days,
        }

        # ---------- 过拟合过滤 ----------
        sr = _annual_sharpe(trade_return, periods_per_year)
        dsr_pval, dsr_val = _deflated_sharpe_pval(trade_return, periods_per_year)
        pbo = _pbo_sharpe_stability(trade_return)
        cagr_val = _cagr(float(df["margin_before"].iloc[0]), float(df["margin_after"].iloc[-1]), total_days)
        max_dd_val, dd_dur, recovery_days, _ = _max_drawdown(margin_curve)
        calmar = _calmar_ratio(cagr_val, max_dd_val)
        sortino = _sortino_ratio(trade_return, periods_per_year)

        overfit = {
            "夏普比率": round(sr, 4),
            "Deflated_Sharpe": round(dsr_val, 4),
            "Deflated_Sharpe_p值": round(dsr_pval, 6),
            "PBO_前半段夏普": round(pbo["SR_first_half"], 4) if pbo["SR_first_half"] is not None else None,
            "PBO_后半段夏普": round(pbo["SR_second_half"], 4) if pbo["SR_second_half"] is not None else None,
            "PBO_衰减比": round(pbo["SR_ratio"], 4) if pbo["SR_ratio"] is not None else None,
            "PBO_判定": pbo["PBO_flag"],
            "卡尔玛比率": round(calmar, 4),
            "索提诺比率": round(sortino, 4),
        }

        # ---------- 成本后生存 ----------
        cvar_95 = _cvar(trade_return, 0.05)
        cvar_99 = _cvar(trade_return, 0.01)

        df["close_date"] = df["closeTime"].dt.date
        daily_pnl = df.groupby("close_date")["profit_Usdt"].sum()
        daily_margin = df.groupby("close_date")["margin_before"].first()
        daily_ret = (daily_pnl / daily_margin).dropna()
        daily_vol = float(np.std(daily_ret, ddof=1)) if len(daily_ret) > 1 else 0.0
        annual_vol = daily_vol * math.sqrt(365)
        vol_deviation = abs(annual_vol - 0.20) / 0.20 * 100 if annual_vol > 0 else None

        survival = {
            "CVaR_95%": round(cvar_95, 6),
            "CVaR_99%": round(cvar_99, 6),
            "日波动率": round(daily_vol, 6),
            "年化波动率": round(annual_vol, 4),
            "目标波动率": 0.20,
            "波动率偏差%": round(vol_deviation, 2) if vol_deviation is not None else "N/A",
        }

        # ---------- 收益属性质量 ----------
        wins = df[df["profit_Usdt"] > 0]
        losses = df[df["profit_Usdt"] < 0]
        total_win = float(wins["profit_Usdt"].sum()) if len(wins) > 0 else 0.0
        total_loss = float(losses["profit_Usdt"].sum()) if len(losses) > 0 else 0.0

        df["month"] = df["closeTime"].dt.to_period("M")
        monthly = df.groupby("month")["profit_Usdt"].sum()
        month_win_rate = float((monthly > 0).sum() / len(monthly) * 100) if len(monthly) > 0 else 0.0

        df["week"] = df["closeTime"].dt.to_period("W")
        weekly = df.groupby("week")["profit_Usdt"].sum()
        week_win_rate = float((weekly > 0).sum() / len(weekly) * 100) if len(weekly) > 0 else 0.0

        total_return_pct = float(
            (df["margin_after"].iloc[-1] - df["margin_before"].iloc[0])
            / df["margin_before"].iloc[0] * 100
        )

        quality = {
            "盈利笔数": len(wins),
            "亏损笔数": len(losses),
            "总盈利金额": round(total_win, 4),
            "总亏损金额": round(total_loss, 4),
            "最大单笔盈利": round(float(wins["profit_Usdt"].max()), 4) if len(wins) > 0 else 0.0,
            "最大单笔亏损": round(float(losses["profit_Usdt"].min()), 4) if len(losses) > 0 else 0.0,
            "年化收益率_CAGR": round(cagr_val * 100, 2),
            "总收益率%": round(total_return_pct, 2),
            "盈亏比": round(abs(total_win / total_loss), 4) if total_loss != 0 else None,
            "盈利因子": round(abs(total_win / total_loss), 4) if total_loss != 0 else None,
            "收益分布偏度": round(_skewness(trade_return), 4),
            "收益分布峰度": round(_kurtosis(trade_return), 4),
            "月胜率%": round(month_win_rate, 2),
            "周胜率%": round(week_win_rate, 2),
        }

        # ---------- 实盘耐受力 ----------
        max_wins, max_losses = _consecutive_streaks(trade_return)
        roll_sr_std = _rolling_sharpe_std(trade_return)
        stressed_profit = _cost_stress_test(df, 2.0)

        mid = n_trades // 2
        if mid >= 2:
            first_half_ret = float(df["profit_Usdt"].iloc[:mid].sum() / df["margin_before"].iloc[0])
            second_half_ret = float(df["profit_Usdt"].iloc[mid:].sum() / df["margin_after"].iloc[mid - 1])
            oos_decay = second_half_ret / first_half_ret if first_half_ret != 0 else None
        else:
            oos_decay = None

        stress = {
            "最大回撤%": round(abs(max_dd_val) * 100, 2),
            "最大回撤_原始值": round(max_dd_val, 4),
            "回撤持续笔数": dd_dur,
            "恢复时间_天": recovery_days,
            "成本压力_2x滑点后利润": round(stressed_profit, 4),
            "成本压力_原始利润": round(net_profit, 4),
            "滚动夏普标准差": round(roll_sr_std, 4),
            "最长连胜": max_wins,
            "最长连败": max_losses,
            "OOS衰减率": round(oos_decay, 4) if oos_decay is not None else None,
        }

        return {
            "基础数据": basic,
            "过拟合过滤": overfit,
            "成本后生存": survival,
            "收益属性质量": quality,
            "实盘耐受力": stress,
        }