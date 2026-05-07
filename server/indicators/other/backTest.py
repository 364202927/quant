from server.indicators.baseIndicators import *
from server.market.consts import kLong,kShort,kBuy,kSell
# open_eff,close时添加冲击成本价,模拟资金量大的情况下对市场的影响

# todo:改版添加指标
# 1.当前的币和收益做一个总收益率
# 2.月度表现
# 3.风险等级评分
# 4.最大回撤，日，周，历史
Year = 365  # 每一年有几天开盘，若是股票252天

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
        # print(self.margin,self.principal)

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
        def _fundingRates(open_time, close_time) -> int:
            """计算持仓期内覆盖的8h结算点次数"""
            funding_times = pd.date_range(start=open_time.floor('D'), end=close_time.ceil('D'), freq='8h')
            return int(((funding_times > open_time) & (funding_times <= close_time)).sum())

        def _process_trajectory(trades: list, dir: str, equity: float, utilization: float):
            """
            处理一条完整的交易轨迹，返回 (总利润, 总手续费, 收益率%, 已用保证金, 是否爆仓)
            """
            # 确定买卖符号和增仓行为
            if dir == "LONG":
                add_behavior = "buy"
                sign = 1
            elif dir == "SHORT":
                add_behavior = "sell"   # 空头用 sell 增仓
                sign = -1
            else:
                raise ValueError(f"Unknown dir: {dir}")

            qty = 0.0              # 当前持仓数量
            avg_cost = 0.0         # 平均持仓成本
            fee_total = 0.0        # 累计手续费
            realized_profit = 0.0  # 已实现盈亏
            max_notional = 0.0     # 期间最大名义价值（用于资金费率估算）
            used_margin_total = 0.0# 累计占用保证金（只增不减，用于收益率计算）

            for i, t in enumerate(trades):
                # --- 计算仓位比例：优先使用 position%，否则使用默认 utilization ---
                if 'position%' in t and pd.notna(t['position%']):
                    pct = t['position%'] / 100.0
                else:
                    pct = utilization   # 默认 0.1

                behavior = t["behavior"]
                price = t["price"]
                lv = t["lv"]

                is_increase = (behavior == add_behavior)    # 增仓动作
                is_last = (i == len(trades) - 1)            # 轨迹最后一个动作（强制平仓）

                # 滑点（每个动作独立生成，开仓/平仓方向对称）
                slip = random.uniform(0.0001, 0.0005)
                if is_increase:
                    eff_price = price * (1 + sign * slip)       # 增仓成交价不利
                else:
                    eff_price = price * (1 - sign * slip)       # 减仓成交价不利

                if is_increase:
                    # --- 增仓（开仓 / 加仓）---
                    margin_used = equity * pct
                    d_qty = margin_used * lv / eff_price
                    if d_qty <= 0:
                        continue
                    fee_trade = d_qty * eff_price * 0.0005   # 开仓手续费
                    fee_total += fee_trade

                    # 更新持仓成本
                    if qty == 0:
                        avg_cost = eff_price
                    else:
                        avg_cost = (qty * avg_cost + d_qty * eff_price) / (qty + d_qty)
                    qty += d_qty
                    used_margin_total += margin_used

                else:
                    # --- 减仓（含部分减仓、全部平仓）---
                    close_qty = qty if is_last else qty * pct   # 最后一笔全平，否则按比例减
                    if close_qty <= 0:
                        continue
                    fee_trade = close_qty * eff_price * 0.0005  # 平仓手续费
                    fee_total += fee_trade

                    # 计算已实现盈亏
                    profit = (eff_price - avg_cost) * close_qty * sign
                    realized_profit += profit

                    qty -= close_qty
                    if qty <= 1e-8:
                        qty = 0.0
                        avg_cost = 0.0
                    # 注意：保证金未释放，但在收益率计算中使用最初累计的 used_margin_total

                # 更新最大名义价值（用于资金费率估算）
                current_notional = qty * eff_price
                if current_notional > max_notional:
                    max_notional = current_notional

            # 若仍有残留仓位（非100%平仓），自动强制平掉
            if qty > 1e-8:
                last_price = trades[-1]["price"]
                slip = random.uniform(0.0001, 0.0005)
                eff_price = last_price * (1 - sign * slip)
                fee_trade = qty * eff_price * 0.0005
                fee_total += fee_trade
                profit = (eff_price - avg_cost) * qty * sign
                realized_profit += profit
                qty = 0.0

            # --- 资金费率（简化估算，仍标记为后续可优化） ---
            open_time = trades[0]["time"]
            close_time = trades[-1]["time"]
            funding_count = _fundingRates(open_time, close_time)
            fee_funding = funding_count * max_notional * 0.0001      # 0.01% 基础费率
            fee_total += fee_funding

            fee_total = round(fee_total, 6)
            profit_usdt = round(realized_profit - fee_total, 4)
            rate = round(profit_usdt / used_margin_total * 100, 2) if used_margin_total else 0.0

            return profit_usdt, fee_total, rate, used_margin_total, False

        # ----------------- 主循环 -----------------
        result = pdData(["dir", "openTime", "duration", "openPrice", "closePrice", "lv",
                        "fee", "profit_Usdt", "rate"])
        blowup = False
        for order in orders:
            first, last = order["trades"][0], order["trades"][-1]
            meta = {
                "dir": order["dir"],
                "openTime": first["time"],
                "duration": last["duration"],
                "openPrice": first["price"],
                "closePrice": last["price"],
                "lv": first["lv"]
            }

            if blowup:
                result.dataConcat({**meta, "fee": 0, "profit_Usdt": 0, "rate": 0})
                continue

            profit, fee, rate, margin_used, _ = _process_trajectory(order["trades"], order["dir"], self.margin, utilization=0.1)

            self.margin += profit
            if self.margin < self.principal * 0.1:
                print("爆仓了")
                blowup = True

            result.dataConcat({**meta, "fee": fee, "profit_Usdt": profit, "rate": rate})

        return result