import numpy as np
from server.strategy.base.baseTrade import *
from server.market import kLong, kShort, kBuy, kSell, kSpot
from server.utils.science import (kFeeRate, kLiqRatio, kMarginRatio, feeCost,
                                  fundingPay, fundingTable, slipPrice, slipRange)

EPS = 1e-8
kContract = 'contract'  # 轨迹类型: 合约;现货用 kSpot
_SIDE = {kLong: 1, kShort: -1}
_DIR = {1: kLong, -1: kShort}

class testTrade(baseTrade):
    "测试交易(本地回测开单)"

    def __init__(self, type=kContract):
        super().__init__()
        self._type = type
        self._feeRate, self._slip = kFeeRate, slipRange()
        self._index, self._funding, self._fTimes = [], {}, []
        self._px, self._idx = 0.0, 0                # feed 喂入的当前收盘价/K线下标
        self.reset()

    # 初始化账号: 本金/费率/滑点, kLine 提供资金费结算点(无 funding_bps 则不结算)
    def initAcc(self, kLine, principal=1000, fee_rate=None, slip=None):
        self._principal = principal
        if fee_rate is not None:
            self._feeRate = fee_rate
        if slip is not None:
            self._slip = slipRange(slip)
        df = kLine.raw().set_index("candle_begin_time")
        self._index, self._funding = df.index, fundingTable(df)
        self._fTimes = sorted(self._funding)
        self.reset()

    def reset(self):
        self._trajectories: list[dict] = []       # 全交易轨迹(兼容 backTest 格式)
        self._records: list[dict] = []            # 交易记录(对齐 realTrade 字段)
        self._positions: dict[int, dict] = {}     # side -> 持仓(同向只有一条未平轨迹)
        self._openTraj: dict[str, int] = {}       # dir -> 未平轨迹下标
        self._cash = getattr(self, "_principal", 0.0) * kMarginRatio
        self._floor = self._cash * kLiqRatio
        self._fPos, self._orderId, self._skipped = 0, 0, 0
        self._blown, self._blownAt = False, None
        self._rng = np.random.default_rng(int(self._slip[2]))

    # ── 净值 = 已实现权益 + 持仓浮盈;保证金按净值计算,与 backTest 一致 ──
    def _nav(self, price):
        return self._cash + sum((price - p["cost"]) * p["qty"] * p["side"] for p in self._positions.values())

    def _usedMargin(self):
        return sum(p["margin"] for p in self._positions.values())

    # 可用保证金(净值-已占用), 供 science.canOrder 判定能否开仓
    def getAvail(self, price):
        return self._nav(price) - self._usedMargin()

    # ── 强平: 净值跌破初始权益的 kLiqRatio 即全部平掉,之后拒绝下单. 策略需逐K线调用才能复现 backTest 的逐K线检查 ──
    def checkLiquidation(self, price, idx):
        if self._blown or self._nav(price) >= self._floor:
            return
        for pos in list(self._positions.values()):
            self._exit(pos, price, idx, pos["qty"])
        self._blown, self._blownAt = True, idx

    # ── 资金费: 把已过结算点的费用补到持仓上(同 backTest: 开仓时刻早于结算时刻才收) ──
    def _settleFunding(self, idx):
        ts = self._index[idx]
        while self._fPos < len(self._fTimes) and self._fTimes[self._fPos] <= ts:
            settleTs = self._fTimes[self._fPos]
            self._fPos += 1
            price, rate = self._funding[settleTs]
            for pos in self._positions.values():
                if self._type == kSpot or self._index[pos["opened_at"]] >= settleTs:
                    continue
                cost = fundingPay(pos["qty"], price, rate, pos["side"])
                if not cost:
                    continue
                self._cash -= cost
                self._records.append({"time": int(self._index.get_indexer([settleTs])[0]), "symbol": pos["symbol"], "orderId": "", "positionSide": _DIR[pos["side"]], "type": self._type, "total": 0, "amount": pos["qty"], "average": price, "leverage": pos["lv"], "fee(BNB)": cost, "profit": -cost, "kind": "funding"})

    # ── 轨迹: 同向未平轨迹追加,已平则新开(多空各一条,天然支持对冲) ──
    def _appendTraj(self, side, trade):
        trajId = self._openTraj.get(_DIR[side])
        if trajId is None:
            trajId = self._openTraj[_DIR[side]] = len(self._trajectories)
            self._trajectories.append({"dir": _DIR[side], "type": self._type, "trades": [trade]})
            return
        self._trajectories[trajId]["trades"].append(trade)

    # ── 开仓: margin 为拟投入保证金,超出可用保证金时缩量;position% 记实际占净值比例 ──
    def _open(self, side, symbol, price, idx, margin, lv):
        if self._blown:
            return
        self._settleFunding(idx)
        nav = self._nav(price)
        margin = min(margin, nav - self._usedMargin())
        if margin <= EPS:
            self._skipped += 1
            return
        px = slipPrice(price, side, self._rng.uniform(self._slip[0], self._slip[1]))
        qty = margin * lv / px
        fee = feeCost(qty, px, self._feeRate)
        self._cash -= fee
        pos = self._positions.setdefault(side, {"side": side, "symbol": symbol, "opened_at": idx, "qty": 0.0, "cost": 0.0, "margin": 0.0, "fee": 0.0, "lv": lv})
        pos["cost"] = (pos["qty"] * pos["cost"] + qty * px) / (pos["qty"] + qty)
        pos["qty"] += qty
        pos["margin"] += margin
        pos["fee"] += fee
        pos["lv"] = lv
        self._orderId += 1
        self._appendTraj(side, {"behavior": kBuy if side == 1 else kSell, "pos": idx, "lv": lv, "position%": round(margin / nav * 100, 6)})
        self._records.append({"time": idx, "symbol": symbol, "orderId": self._orderId, "positionSide": _DIR[side], "type": self._type, "total": margin, "amount": qty, "average": px, "leverage": lv, "fee(BNB)": fee, "profit": 0, "kind": "open"})
        self.checkLiquidation(price, idx)

    # ── 平仓: 滑点取不利方向;开仓手续费已在建仓时扣除,这里只结平仓手续费
    # lv 缺省沿用持仓杠杆, 仅用于轨迹/记录的 leverage 字段(平仓杠杆不参与盈亏) ──
    def _exit(self, pos, price, idx, qty, lv=None):
        if qty <= EPS:
            return
        side, frac = pos["side"], min(qty / pos["qty"], 1.0)
        lv = lv or pos["lv"]
        px = slipPrice(price, -side, self._rng.uniform(self._slip[0], self._slip[1]))
        feeClose, feeOpen, margin = feeCost(qty, px, self._feeRate), pos["fee"] * frac, pos["margin"] * frac
        gross = (px - pos["cost"]) * qty * side
        self._cash += gross - feeClose
        pos["qty"] -= qty
        pos["fee"] -= feeOpen
        pos["margin"] -= margin
        full = pos["qty"] <= EPS
        if full:
            pos["qty"] = 0.0
        self._orderId += 1
        self._appendTraj(side, {"behavior": kSell if side == 1 else kBuy, "pos": idx, "lv": lv, "position%": 100 if full else round(frac * 100, 6)})
        # fee(BNB) 只记本笔成交手续费,profit 为含开仓手续费分摊的本笔已实现盈亏
        self._records.append({"time": idx, "symbol": pos["symbol"], "orderId": self._orderId, "positionSide": _DIR[side], "type": self._type, "total": margin, "amount": qty, "average": px, "leverage": lv, "fee(BNB)": feeClose, "profit": gross - feeOpen - feeClose, "kind": "close"})
        if not full:
            return
        self._positions.pop(side, None)
        self._openTraj.pop(_DIR[side], None)

    # ── 下单接口: 签名与 realTrade 一致. 模拟按 feed 的收盘价即时成交(含滑点),
    # orderBook/price/inForce/exName 无意义被忽略, 限价单会按市价成交 ──
    # 框架/策略每根K线决策前调用: 保存当前收盘价与K线下标, 下单时取用(实盘由交易所给价)
    def feed(self, price, idx):
        self._px, self._idx = price, idx

    # totelPrice: 数字=名义金额; 'bet:N'=base 的 N%
    @staticmethod
    def _notional(totelPrice, base):
        if isinstance(totelPrice, str) and totelPrice.startswith('bet:'):
            return float(totelPrice[4:]) * 0.01 * base
        return float(totelPrice)

    # ── 合约: 保证金 = 名义金额 / 杠杆, lv=0 取默认杠杆 ──
    def _openOrder(self, side, symbol, totelPrice, lv):
        lv = lv or self._defLv
        notional = self._notional(totelPrice, self.getAvail(self._px))
        self._open(side, symbol, self._px, self._idx, notional / lv, lv)

    def openLong(self, symbol, totelPrice, orderBook=0, price=None, lv=0, inForce='GTC', exName=None):
        self._openOrder(1, symbol, totelPrice, lv)

    def openShort(self, symbol, totelPrice, orderBook=0, price=None, lv=0, inForce='GTC', exName=None):
        self._openOrder(-1, symbol, totelPrice, lv)

    # totelPrice: 'bet:N'=平 N% 持仓; 数字=按金额折算数量并封顶
    def closePos(self, symbol, dir, totelPrice='bet:100', orderBook=0, price=None, lv=0, inForce='GTC', exName=None):
        if self._blown:
            return
        px, idx = self._px, self._idx
        self._settleFunding(idx)
        # 'all' 时按轨迹先后平仓,与 backTest 同一时刻事件按 traj_id 排序的口径一致
        dirs = sorted((kLong, kShort) if dir == 'all' else (dir,), key=lambda d: self._openTraj.get(d, -1))
        for d in dirs:
            pos = self._positions.get(_SIDE.get(d))
            if pos is None or pos["symbol"] != symbol:
                continue
            if isinstance(totelPrice, str) and totelPrice.startswith('bet:'):
                qty = pos["qty"] * min(float(totelPrice[4:]), 100) / 100
            else:
                qty = min(pos["qty"], float(totelPrice) / px)
            self._exit(pos, px, idx, qty, lv or None)
        self.checkLiquidation(px, idx)

    # ── 现货: 按金额买入、按比例卖出,lv 固定 1 ──
    def buy(self, symbol, totelPrice, orderBook=0, price=None, inForce='GTC', exName=None):
        self._open(1, symbol, self._px, self._idx, self._notional(totelPrice, self.getAvail(self._px)), 1)

    def sell(self, symbol, totelPrice='bet:100', orderBook=0, price=None, inForce='GTC', exName=None):
        self.closePos(symbol, kLong, totelPrice)

    # 模拟全部即时成交, 没有挂单可撤
    def cencel(self, symbol, orderID='', exName=None):
        pass

    # ── 接口 ──
    # 交易轨迹(兼容 backTest 的 trades 格式)
    def getTrajectories(self) -> list:
        return self._trajectories

    def getRecords(self) -> list:
        return self._records

    # 账户快照: cash 为已实现权益, used_margin 为占用保证金, blowup 为强平标记
    def getAccount(self) -> dict:
        return {"cash": round(self._cash, 4), "used_margin": round(self._usedMargin(), 4), "floor": round(self._floor, 4), "blowup": self._blown, "blowup_at": self._blownAt, "skipped_opens": self._skipped}
