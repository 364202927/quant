from indicators.baseIndicators import *
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from collections import defaultdict


class orderFlow(baseIndicators):
    '交易深度'

    _exs = []    # 交易所列表
    _head = []  # todo可不要
    _exsPf = None  # todo可不要
    # todo:可计算cvd
    # todo:添加上op持仓

    _depthPf, _tradePf = None, None

    # 深层数据和成交记录
    depthData = []
    tradeData = {}
    # symbols = []
    # limit = 0

    def info(self):
        return "深度分析数据"

    def init(self):
        # limit = 100
        pass

    def delimit(self, **kWargs):
        if kWargs.get('exs'):
            self._exs = kWargs['exs']
        self._exsPf = None
        self._head = []
        # if kWargs.get('symbols'):self.symbols = kWargs['symbols']
        # if kWargs.get('limit'):self._ex = kWargs['limit']

        # print(self._ex.depth('BTCUSDT'))

    # dom
    def depth(self, symbol, weight=[], limit=500):
        depthData = []
        with ThreadPoolExecutor(max_workers=len(self._exs)) as executor:
            for ex in self._exs:
                data = ex.depth(symbol, limit)
                data['name'] = ex.name()
                depthData.append(data)

        # print("~~~~depth数据~~~")
        # print(depthData)
        # 对每个订单簿按统一价格档位归一化（如 round(price, 2)）#
        # a_price,a_amount,b_price,b_amount, ...
        self._exsName = [
            'side'] + [f"{data['name']}_{item}" for data in depthData for item in ['price', 'amount']]
        bids, asks = [], []
        for i in range(limit):
            bids.append(
                ["bid"] + [item for data_item in depthData for item in data_item['bids'][i]])
            asks.append(
                ["ask"] + [item for data_item in depthData for item in data_item['asks'][i]])
        self._exsPf = pdData(head=self._exsName, xmlData=bids + asks)
        # 合并数据
        return self._bucketMerge(priceStep=1, weight=weight)


# 	流动性分析需额外注意：
# 时间衰减处理：对旧数据降权（如5分钟前数据权重=0.2）
# 交易所信用区分：对深度数据的可靠性打分（如Binance数据权重>小交易所）
# 可视化辅助：热力图展示不同价格区间的合并深度


# 关键观察
# 买盘流动性集中：
# 在105177-105179区间有大量买单堆积，特别是A交易所在105179区间有16.788的大单
# B交易所在105177区间有9.774的买单集中
# 卖盘流动性分布：
# 卖单主要集中在105177和105180附近
# 整体卖盘量比买盘量小很多，显示当前市场可能偏向买方
# 价格缺口：
# 在105170-105174区间几乎没有买单，可能形成下方支撑薄弱区域
# 这种分组方式可以帮助交易者快速识别关键价格水平的流动性分布，为订单流策略提供直观的市场深度视图。

    # 区间价格合并


    def _bucketMerge(self, priceStep, weight=[]):
        exsName = [ex.name() for ex in self._exs]
        exSize = len(exsName)
        if not len(weight):  # 流动性加权合并
            totalLiquidity = []
            # 各交易所总流动性
            totalLiquidity = [
                round(self._exsPf.get()[f"{exName}_amount"].astype(float).sum(), 4)
                for exName in exsName]
            # 根据流动性计算交易所权重
            total = sum(totalLiquidity)
            weight = [round(liq / total, 2) for liq in totalLiquidity]
        # 按价格区间合并
        tmpBucket = defaultdict(lambda: [0, 0] + [0] * 2 * exSize)
        for i in range(len(self._exsPf.get())):
            pf = self._exsPf.get(i)
            for j in range(exSize):
                exName = exsName[j]
                # 计算价格区间（用 round 替代手动取整）
                price = float(pf[exName + '_price'])
                price_bucket = int(price // priceStep) * priceStep
                # 根据买卖方向累计数量
                amount = float(pf[exName + '_amount'])
                index = 0 if pf['side'] == 'bid' else 1
                exWeight = weight[j] if j < len(weight) and weight[j] else 1
                tmpBucket[price_bucket][index] += amount * exWeight
                # 保留各交易所交易量
                exDom = exSize + exSize * j + index + \
                    1 if exSize == 1 else exSize + exSize * j + index
                tmpBucket[price_bucket][exDom] += amount

        # print("~~~~~~",tmpBucket)
        head = ['bucketPrice', 'bid', 'ask'] + \
            [f"{exName}_{side}" for exName in exsName for side in ['bid', 'ask']]
        res = [[bucket] + amounts for bucket, amounts in tmpBucket.items()]
        merged = pdData(head=head, xmlData=res)
        merged._resetFormat()
        return merged

    # 足迹图
    def trades(self, symbol, priceStep=1, limit=1000):
        def resample2Time(
            df,
            time,
            dict={
                'mean': 'price',
                'max': 'price',
                'min': 'price',
                'qty': 'qty',
                'count': 'qty'}):
            df['buy_qty'] = df['qty'].where(df['side'] == 'buy', 0)
            df['sell_qty'] = df['qty'].where(df['side'] == 'sell', 0)
            agg = df.resample(time).agg(
                priceMean=(dict['mean'], 'mean'),
                priceMax=(dict['max'], 'max'),
                priceMin=(dict['min'], 'min'),
                qty_sum=(dict['qty'], 'sum'),
                qty_count=(dict['count'], 'count'),
                qty_buy=('buy_qty', 'sum'),
                qty_sell=('sell_qty', 'sum'))
            # agg['delta'] = agg['qty_buy'] - agg['qty_sell'] 		#量差
            # agg['price_range'] = agg['priceMax'] - agg['priceMin']	#价差
            # [['priceMean','priceMax','priceMin' 'price_diff','qty_count','qty_sum', 'qty_buy','qty_sell', 'delta']]
            return agg

        # logic
        tradeHistory = []
        with ThreadPoolExecutor(max_workers=len(self._exs)) as executor:
            for ex in self._exs:
                data = {
                    'name': ex.name(),
                    'trades': ex.trades(symbol, limit)
                }
                tradeHistory.append(data)

        # test数据
        # print("~~~~交易数据~~~")
        # print(tradeHistory)
        for data in tradeHistory:
            exName = data['name']
            exTradeData = []
            for trade in data['trades']:
                # todo:由于从交易所获取交易数据有可能会重复，这里需要根据id去剔除已有的数据
                time_ms = pd.to_numeric(trade['time'], errors='coerce')
                time_dt = pd.to_datetime(time_ms, unit='ms')
                exTradeData.append({'time': time_dt,
                                    'price': float(trade['price']),
                                    'qty': float(trade['qty']),
                                    'quoteQty': float(trade['quoteQty']),
                                    # 主动挂单
                                    'side': 'sell' if trade['isBuyerMaker'] else 'buy',
                                    })
            # pd
            tradePf = pdData(
                head=[
                    'price',
                    'qty',
                    'quoteQty',
                    'time',
                    'side'],
                xmlData=exTradeData)
            tradePf.get().set_index('time', inplace=True)
            # tradePf.show()
            tradePf.format(resample2Time(tradePf.get(), '1s'), style='copy')
            # 记录交易所数据
            if self.tradeData.get(exName) is None:
                self.tradeData[exName] = tradePf
                continue
            self.tradeData[exName].pfConcat(tradePf.get(), reset=False)

        print("~~~~交易数据~~~")
        self.tradeData['binance'].show()
        # todo:如果是多交易所的处理是把数据都合并一起
        self.tradesAnalyze2(self.tradeData['binance'].copy())

    # 交易分析 mAndV(动量和波动周期)[3,5,5~10],wall(墙)[1.2~2, 0.1~0.5(小币种需要设置更小),
    # 0.05~0.2允许2秒间最大浮动]
    def tradesAnalyze2(self, df, mAndV=[3, 5, 5], wall=[1.5, 0.3, 0.05]):
        # if len(df) < 20: return# 数据量太少，不做分析
        df['delta'] = df['qty_buy'] - df['qty_sell']  # 量差
        df['price_range'] = df['priceMax'] - df['priceMin']  # 价差
        df['buy_ratio'] = df['qty_buy'] / \
            (df['qty_buy'] + df['qty_sell'] + 1e-8)  # 成交偏向
        df['avg_trade_size'] = df['qty_sum'] / \
            (df['qty_count'] + 1e-8)  # 平均单笔成交
        #
        df['momentum'] = df['priceMean'] - \
            df['priceMean'].shift(mAndV[0])  # 动量
        df['volatility'] = df['priceMean'].rolling(
            window=mAndV[1]).std()  # 波动率
        df['rolling_qty'] = df['qty_sum'].rolling(
            window=mAndV[2]).mean()  # 成交量均价
        # 1. 交易墙（支撑或阻力）：高成交量 + 波动极小 + 均价几乎不变
        df['is_trade_wall'] = ((df['qty_sum'] > df['rolling_qty'] * wall[0]) &
                               (df['price_range'] < wall[1]) &
                               (df['priceMean'].diff().abs() < wall[2]))
        # 2. 主动买入/卖出异常爆发
        df['is_buy_surge'] = (df['buy_ratio'] > 0.9) & (
            df['qty_buy'] > df['qty_buy'].rolling(10).mean() * 2)
        df['is_sell_surge'] = (df['buy_ratio'] < 0.1) & (
            df['qty_sell'] > df['qty_sell'].rolling(10).mean() * 2)
        # 3. 高波动标记
        df['is_high_volatility'] = df['volatility'] > df['volatility'].rolling(
            20).mean() * 2
        # 4. 成交量激增
        df['is_volume_spike'] = df['qty_sum'] > df['qty_sum'].rolling(
            10).mean() * 2
        # 可视化用字段（评分型）
        df['wall_strength'] = df['is_trade_wall'].astype(
            int) * df['qty_sum'] * (1 - df['price_range'])
        df.fillna(0, inplace=True)

        # print(df[['priceMean','priceMax','priceMin' 'price_diff','qty_count','qty_sum', 'qty_buy','qty_sell', 'delta']])
        print(df)
        # 关键信息
        key_events = df[df['is_trade_wall'] | df['is_buy_surge']
                        | df['is_sell_surge'] | df['is_volume_spike']]
        print(key_events)

    def tradesAnalyze(self, priceStep=1):
        # df = self._tradePf.copy()
        def tradeIntensity(window='1s', threshold=0.05):
            df = self._tradePf.get().set_index('time')
            rolling = df['qty'].rolling(window)
            df['rolling_qty'] = rolling.sum()
            # 主动买/卖量
            df['buy_qty'] = (df['side'] == 'buy') * df['qty']
            df['sell_qty'] = (df['side'] == 'sell') * df['qty']
            df['rolling_buy'] = df['buy_qty'].rolling(window).sum()
            df['rolling_sell'] = df['sell_qty'].rolling(window).sum()
            # 成交强度得分（买卖差 / 总成交量）
            df['intensity_score'] = (
                df['rolling_buy'] - df['rolling_sell']) / (df['rolling_qty'] + 1e-8)
            # 标记高强度区域（正为买盘强度，负为卖盘强度）
            df['intense_buy'] = df['intensity_score'] > threshold
            df['intense_sell'] = df['intensity_score'] < -threshold
            return df.reset_index()

        def tradeSpeed(price_jump_threshold=0.5, time_window=1.0):
            df = self._tradePf.copy()
            df['price_diff'] = df['price'].diff()
            df['direction'] = df['side'].map({'buy': 1, 'sell': -1})
            df['price_move'] = df['price_diff'] * df['direction']  # 趋势方向下的价格跳动

            # 吃单速度：在方向一致时，价格跳动 >= 阈值，并时间小于窗口
            df['aggressive_jump'] = (
                (abs(df['price_move']) >= price_jump_threshold)
                & (df['time_diff'] <= time_window)
            )

            # 可进一步计算滑动窗口下的频率
            df['aggressive_rate'] = df['aggressive_jump'].rolling(10).sum()
            return df

        def supportWalls(price_round=1.0, volume_threshold=2.0):
            df = self._tradePf.copy()
            df['price_bucket'] = (
                df['price'] / price_round).round() * price_round
            wall_df = df.groupby(['price_bucket', 'side'])[
                'qty'].sum().unstack().fillna(0)

            wall_df['type'] = None
            wall_df['support'] = (wall_df['buy'] >= volume_threshold)
            wall_df['resistance'] = (wall_df['sell'] >= volume_threshold)
            wall_df['type'] = np.where(
                wall_df['support'], 'support', np.where(
                    wall_df['resistance'], 'resistance', None))

            return wall_df.reset_index().dropna(subset=['type'])

        # window = '1s'   # 可改成 '200ms' 做更细颗粒度分析
        # df['side_numeric'] = df['side'].map({'buy': 1, 'sell': -1})
        # df['signed_qty'] = df['qty'] * df['side_numeric']
        # # 成交强度
        # df['buy_vol'] = df[df['side'] == 'buy']['qty'].rolling(window).sum()
        # df['sell_vol'] = df[df['side'] == 'sell']['qty'].rolling(window).sum()
        # df['total_vol'] = df['buy_vol'].fillna(0) + df['sell_vol'].fillna(0)
        # #吃单速度
        # df['buy_count'] = df[df['side'] == 'buy']['qty'].rolling(window).count()
        # df['sell_count'] = df[df['side'] == 'sell']['qty'].rolling(window).count()
        # #价格变化
        # df['price_change'] = df['price'].diff()

        # # ===阻力/支撑墙检测===
        # df['price_bucket'] = (df['price'] // priceStep) * priceStep
        # support_resist = df.groupby('price_bucket').agg({# 分组统计：哪个价格区间交易最多
        # 	'qty': 'sum',
        # 	'side_numeric': ['sum', 'count']
        # })
        # support_resist.columns = ['total_qty', 'net_qty', 'trade_count']
        # support_resist['avg_trade_size'] = support_resist['total_qty'] / support_resist['trade_count']
        # support_resist = support_resist.sort_values('total_qty', ascending=False)
        # if len(support_resist) > 1:
        # 	df['price_momentum'] = df['price'].rolling(window).apply(lambda x: x.iloc[-1] - x.iloc[0], raw=True)

        # 大于 95% 的就是大单
        # q95 = df['qty'].quantile(0.95)
        # df['is_large_trade'] = df['qty'] > q95

        # print("~~~~trades~~~~~~")
        ti = tradeIntensity()
        ts = tradeSpeed()
        sw = supportWalls()
        print('~~~~tradeIntensity~~~~')
        print(ti)
        print('~~~~speed~~~~')
        print(ts)
        print("~~~~支持/阻力墙~~~~~~")
        print(sw)
        # print(support_resist)

    def calculate(self, pd):
        pass

    # 默认指标
    # _maDay = 30  		#均线：交易时间线，股票是20天，币是30天
    # _stDev = 2 			#标准差：数字越大开口越阔，触发的信号越不频繁

    # def init(self):
    # 	self._pd.setHead(['candle_begin_time', "median", "std", "upper", "lower",'bbw','%B'])

    # def delimit(self, **kWargs):
    # 	if kWargs.get('maDay'): self._maDay = kWargs['maDay']
    # 	if kWargs.get('stdev'): self._stdev = kWargs['stdev']

    # def calculate(self, pd):
    # 	self._pd.format(pd, style="copy")
    # 	self._bollTrack(pd)
    # 	return self._pd

    # #计算均线和boll上下轨
    # def _bollTrack(self, sor_pd):
    # 	pd = self._pd.get()
    # 	#均线 = n天收盘价的 公式：a = 平均值(1+...)/n  b = sum((当前值-a)平方) c = 根号(b/(len - 1))
    # 	pd['median'] = sor_pd['close'].rolling(window = self._maDay).mean()
