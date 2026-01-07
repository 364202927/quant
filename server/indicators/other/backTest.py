from indicators.baseIndicators import *
# todo:对应未来的拓展修改
# 1.开多对应是0.1~1对应是仓位的百分比，减仓为0全平，-0.n仓位，最终仓位1-%n(当前减仓百分比，最终仓位为0全平)
# 2.开空对应是-0.1~-1其他同上
# 3.最终数据为{'signal': 'long', 'open':[index1,index2,...],'end':[index1,index2,...] }
# 4.爆仓的话没算

# todo:改版添加指标
# 1.当前的币和收益做一个总收益率
# 2.月度表现
# 3.风险等级评分
# 4.最大回撤，日，周，历史
Market_Fee = True
Year = 365  # 每一年有几天开盘，若是股票252天


class backTest(baseIndicators):
    "回测数据：性能测试"
    # amount,ftc,ptc= 0,0,0 #初始资金，固定成本，可变成本
    exchangeName = ''
    level = 1  # 杠杆
    principal = 0  # 本金
    # margin = 0             #保证金
    orderQua = 0  # 订单数量
    # todo:滚仓或固定金额

    def init(self):
        self.principal = 1000
        # self.margin = 1000
        self.level = 1

    def delimit(self, **kWargs):
        if kWargs.get('principal'):
            self.principal = kWargs['principal']
        # if kWargs.get('margin'): self.margin = kWargs['margin']
        if kWargs.get('lv'):
            self.level = kWargs['lv']

    def calculate(self, df, orders):
        # 1.找出每一笔订单
        self.orderQua = 0
        orders = self._filter(orders)
        # 2.对每笔订单计算利润
        originalPrincipal = self.principal
        print(
            "本金:",
            originalPrincipal,
            ' 杠杆:',
            self.level,
            " 策略交易：",
            self.orderQua)
        orders_Statistical = self._equityCurve(df, orders)
        # 3.该策略总收益统计
        annualized_return, sharpe_ratio, sortino_ratio, calmar_ratio, daily_volatility, annual_volatility, max_drawdown, ddIdx = self._incomeMetrics(
            df, orders_Statistical, originalPrincipal)
        # 4.最终收益并打印
        printdf = orders_Statistical.get()
        lastOrder = printdf.iloc[-1]
        # balance = self.margin#self.principal# + lastOrder['profit(u)'] -
        # lastOrder['transactionFee']
        winDf = printdf[printdf['profit(u)'] > 0]
        lostDf = printdf[printdf['profit(u)'] <= 0]
        print(printdf)
        print(
            "胜率: {:.2f}%    剩余资金: {}u   净利润: {}u     总佣金: {:.2f}u".format(
                len(winDf) / len(printdf),
                self.principal,
                self.principal - originalPrincipal,
                printdf['transactionFee'].sum()))
        print(
            "获利次数: {}     平均盈利: {:.2f}u   总盈利: {}u     最大盈利: {}u".format(
                len(winDf),
                winDf['profit(u)'].sum() /
                len(winDf),
                winDf['profit(u)'].sum(),
                winDf['profit(u)'].max()))
        print(
            "亏损次数: {}     平均亏损: {:.2f}u   总亏损: {}u     最大亏损: {}u".format(
                len(lostDf),
                lostDf['profit(u)'].sum() /
                len(lostDf),
                lostDf['profit(u)'].sum(),
                lostDf['profit(u)'].min()))
        print('~~~~~~收益指标~~~~~~~')
        print(
            "年化收益:",
            annualized_return,
            '   总收益:{}%'.format(
                round(
                    printdf['rate(%)'].sum(),
                    1)))
        print(
            "盈亏比:{:.2f}%".format(
                (winDf['profit(u)'].sum() +
                 lostDf['profit(u)'].sum()) /
                originalPrincipal))
        print("夏普比率:", sharpe_ratio)
        print('~~~~~~风险指标~~~~~~~')
        print("最大回撤:", round(max_drawdown, 2), '    时间是:{} ~ {}'.format(
            printdf.iloc[ddIdx[0]]['time'], printdf.iloc[ddIdx[1]]['time']))
        print("卡玛比率:", calmar_ratio)
        print("索提诺比率:", sortino_ratio)
        # 年波动率描述 低：回报率为3%，在5%波动率下，回报可能在-2%到8%之间。
        # 中：回报率为6%，在15%的波动率情况下，最终回报有可能在-9%到21%，高：回报率为8%，在30%波动率下回报可能在-22%到38%之间。
        print(
            '日波动率: {:.2f}%    年波动率: {:.2f}%'.format(
                daily_volatility,
                annual_volatility))

    # 过滤出每一笔交易
    def _filter(self, orders):
        all_trades = []
        for order in orders:
            pos = []
            self.orderQua += 1
            for i in range(len(order['position'])):
                indexOrder = order['position'][i]
                pos.append({indexOrder['idx']: indexOrder["position"]})
            all_trades.append({'dir': order['dir'], 'ctaOrders': pos})
        return all_trades
    # 计算每笔订单的利润

    def _equityCurve(self, df, oreders):
        allStatistical = []
        for order in oreders:
            openList, close = [], 0
            for i in range(len(order['ctaOrders'])):
                indexOrder = order['ctaOrders'][i]
                for idx, pos in indexOrder.items():
                    if (order['dir'] == -1 and pos < 0) or \
                            (order['dir'] == 1 and pos > 0):  # 开仓
                        df.loc[idx, order["dir"] ==
                               1 and "signal_long" or 'signal_short'] = order["dir"]
                        openList.append({'idx': idx, 'pos': pos})
                        continue
                    close = {'idx': idx, 'pos': pos}
                    rtPd = self.orderIncome(order['dir'], df, openList, close)
                    allStatistical.append(rtPd.get())
                    df.loc[idx, order["dir"] ==
                           1 and "signal_long" or 'signal_short'] = 0
                    # 计算剩余保证金价格
                    self.principal = self.principal + \
                        rtPd.get(0)['profit(u)'] - rtPd.get(0)['transactionFee']  # 滚仓计算
                    if self.principal < 0:  # 实际上，不等于0就会爆仓
                        print("爆仓了")
                        return
        # 返回统计后的pd
        orders_Statistical = pdData(allStatistical[0].columns.tolist())
        orders_Statistical.format(allStatistical, 'concat')
        return orders_Statistical

    # 每一张单子收益计算
    # todo:roi
    # todo:每8小时0.01% 8小时 资金费率
    def orderIncome(self, dir, df, openList, close):
        slippage = 0.001  # 滑点

        def openPrice():
            # 总成本 = (60000 * 0.1) + (62000 * 0.2) = 6000 + 12400 = 18400
            # 总数量 = 0.1 + 0.2 = 0.3 BTC
            # 平均入场价格 = 118000 ÷ 2 = 59000
            cost, qua = 0, 0
            if len(openList) < 1:
                closePos = df.iloc[openList[-1]['idx']]['close']
                return round(closePos + slippage * closePos, 2)
            # 计算平均开仓价
            for open in openList:
                closePos = df.iloc[open['idx']]['close']
                price = round(closePos + slippage * closePos, 2)
                amount = 1000 / price  # todo:每次保证金的数据都不一样所以这个值会有偏差
                cost += price * amount
                qua += amount
            return cost / qua
        #
        openPf = df.iloc[openList[-1]['idx']]
        closePf = df.iloc[close['idx']]
        # 返回rt(开单时间, 方向, 持续时间, 占几根k线,保证金,倍率, 开仓价,平仓价,数量, 手续费,收益(u),收益率(%))
        rt_pd = pdData(['time',
                        'dir',
                        "duration(min)",
                        "margin",
                        "leverage",
                        "openingPrice",
                        'closingPrice',
                        'quantity',
                        'transactionFee',
                        'profit(u)',
                        'rate(%)'])
        rt_pd.format({'time': [1], 'margin': [1], 'openingPrice': [1], 'closingPrice': [1], 'quantity': [1], 'transactionFee': [0], 'profit(u)': [1], 'rate(%)': [1],
                      'dir': dir,
                      'duration(min)': (closePf['candle_begin_time'].timestamp() - openPf['candle_begin_time'].timestamp()) // 60,
                      # 'section':close['idx'] - openList[-1]['idx'], #合约花了多少根k线
                      'leverage': self.level})
        pf = rt_pd.get()
        pf['time'] = openPf['candle_begin_time']
        # 开仓价,平仓价,保证金
        pf['openingPrice'] = openPrice()
        pf['closingPrice'] = round(
            closePf['close'] + slippage * closePf['close'], 2)
        amountUsed = self.principal * abs(openList[-1]['pos'] * 0.01)
        pf['margin'] = amountUsed * self.level  # todo：滚仓模式
        pf['quantity'] = pf['margin'] / pf['openingPrice']
        # 手续费 = 开仓+平仓（市价，限价不一样）       每家交易所的手续费都是不一样的
        limit = amountUsed * 0.0002
        market = amountUsed * 0.0005
        fundingRate = (pf['duration(min)'] / 480).astype(int) * \
            amountUsed * 0.0001  # 资金费率不是固定的
        fee = Market_Fee and market or limit
        pf['transactionFee'] = round(fee * 2 + fundingRate, 6)
        # 计算收益
        pf['profit(u)'] = contractProfit(
            pf['openingPrice'], pf['closingPrice'], pf['quantity'])
        pf['rate(%)'] = (pf['profit(u)'] / pf['margin'] * 100).round(2)
        return rt_pd

    def _incomeMetrics(self, df, order, principal):
        def calculate_dd(df):
            cumulative_max = df["rate(%)"].cummax()
            df["drawdown"] = cumulative_max - df["rate(%)"]
            max_drawdown_idx = df["drawdown"].idxmax()
            if max_drawdown_idx == 0:  # 特殊情况处理：序列开头即为最大回撤
                return 1, [0, 0]
            max_rate_idx = df.loc[:max_drawdown_idx, "rate(%)"].idxmax()
            # 计算最大回撤值
            max_drawdown = (df.loc[max_rate_idx,
                                   "rate(%)"] - df.loc[max_drawdown_idx,
                                                       "rate(%)"]) / (1 + df.loc[max_rate_idx,
                                                                                 "rate(%)"]) * 100
            return max_drawdown, [max_rate_idx, max_drawdown_idx]
        orderDf = order.get()
        totelDay = (df.iloc[-1]['candle_begin_time'] -
                    df.iloc[0]['candle_begin_time']).days
        totleProfit = orderDf['profit(u)'].sum()
        dailyDf = orderDf['profit(u)'] / orderDf['margin']  # 每日收益
        # 年化收益 (1 + 总收益率)^(每年有几天交易日 / N) - 1
        annualized_return = round(
            ((1 + totleProfit / principal) ** (Year / totelDay) - 1) * 100, 2)
        # 夏普比率 (平均收益率 - 无风险利率) / 收益率标准差
        # ::投资回报与多冒风险的比例：>1，代表基金报酬率高过波动风险；<1，代表基金操作风险大过于报酬率
        sharpe_ratio = round(dailyDf.mean() / dailyDf.std() * np.sqrt(Year), 2)
        # 索提诺比率 = (投资组合平均收益率 - 无风险利率) / 下行风险 ::与夏普类似
        downside_std = dailyDf[dailyDf < 0].std()
        sortino_ratio = round(dailyDf.mean() / downside_std * np.sqrt(Year), 2)
        # 最大回撤 max(累计收益率 - 历史最高点) / 历史最高点
        max_drawdown, idx = calculate_dd(orderDf)
        # 卡玛比率 = 年化收益率 / 最大回撤                 ::理论上讲，卡玛比率值越高越好
        calmar_ratio = round(annualized_return / max_drawdown, 2)
        # 波动率
        daily_volatility = np.std(orderDf['rate(%)'], ddof=1)
        annual_volatility = daily_volatility * np.sqrt(Year)
        return annualized_return, sharpe_ratio, sortino_ratio, calmar_ratio, daily_volatility, annual_volatility, max_drawdown, idx

    # 对以上指标进行分析
    def _analyze(self):
        # 1.指标分析
        # 2.风险风险
        # 3.优化建议
        print("分析")


# 风险管控 1:2
# https://www.youtube.com/watch?v=S6B7ou9i29Q
