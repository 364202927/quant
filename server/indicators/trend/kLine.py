from indicators.baseIndicators import *

from datetime import datetime
from dateutil.relativedelta import relativedelta


import matplotlib.pyplot as plt
# 1,支撑阻力位
# 2.斐波纳指
# 3.趋势线
# 4.vwap
import mplfinance as mpf


class kLine(baseIndicators):
    '整理k线'

    _ex = None  # 交易所
    _symbols = {}  # 交易对

    def init(self):
        pass

    def delimit(self, **kWargs):
        if kWargs.get('ex'):
            self._ex = kWargs['ex']
        if kWargs.get('symbols'):  # 交易对
            symbolsTab = kWargs['symbols']
            for symbol in symbolsTab:
                fileName = self._ex.name() + '_' + symbol + '.csv'
                year_ago = datetime.now() - relativedelta(years=1)
                # print("~~~~~~~~klne~~~~~",fileName, year_ago)
                candle = pdData()
                if not candle.readFile(fileName):  # 不存在文件
                    candle.setPf(
                        self._ex.getHistoryCandles(
                            symbol, [
                                year_ago, 'now']))
                    candle.save2File(fileName)
                else:  # 存在文件
                    diff_seconds = diff_Pdtime(candle.get(-1, 0))
                    # 更新最新k线数据
                    if diff_seconds >= 5:
                        candle.pfConcat(self._ex.getHistoryCandles(
                            symbol, [str(candle.get(-1, 0)), 'now']))
                        candle.save2File(fileName)
                # todo:前面残缺不会补，只补了后面
                # todo:检查数据，如中间漏掉没补
                self._symbols[symbol] = {
                    'name': symbol,  # todo:可以不要
                    'pd': candle
                }
                # 剪裁数据
                # candle.show()
        print(self._symbols['swap_BTCUSDT']['pd'].get())
        # self.marketStructure(self._symbols['swap_BTCUSDT']['pd'].get())
        self.gptMarketStructure(self._symbols['swap_BTCUSDT']['pd'].get())

    def calculate(self):
        # 1.计算日线的支撑
        # 2.辨认趋势顶顶高，底底高
        pass

    # 市场结构
    def gptMarketStructure(self, df):
        def identify_swings(prices, order=3):
            swing_high, swing_low = [], []
            for i in range(order, len(prices) - order):
                window = prices[i - order:i + order + 1]
                if prices[i] == max(window):
                    swing_high.append(i)
                elif prices[i] == min(window):
                    swing_low.append(i)
            return swing_high, swing_low

        def find_last_trend_segment(df, swing_high, swing_low):
            swings = sorted([(i, 'H') for i in swing_high] +
                            [(i, 'L') for i in swing_low])
            if len(swings) < 3:
                return 0, len(df) - 1  # 数据不足时，从头算

            # 从最后往前找，直到趋势方向发生改变
            for j in range(len(swings) - 3, -1, -1):
                i1, t1 = swings[j]
                i2, t2 = swings[j + 1]
                i3, t3 = swings[j + 2]

                # 判断趋势方向是否确认（高点抬高+低点抬高，或相反）
                if t1 == 'L' and t2 == 'H' and t3 == 'L':
                    # 低-高-低 → 下降趋势确认
                    return i1, len(df) - 1
                elif t1 == 'H' and t2 == 'L' and t3 == 'H':
                    # 高-低-高 → 上升趋势确认
                    return i1, len(df) - 1
            return swings[-3][0], len(df) - 1  # 默认从倒数第三个 swing 开始

        # 首先转换时间列并设置为索引
        df['candle_begin_time'] = pd.to_datetime(df['candle_begin_time'])
        df.set_index('candle_begin_time', inplace=True)
        # 然后进行resample操作
        df = df.resample('1H').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'vol': 'sum'
        })
        # df = df.tail(100) #todo：为了不渲染那么多k线

        swing_high, swing_low = identify_swings(df['close'].values, order=3)
        start_idx, end_idx = find_last_trend_segment(df, swing_high, swing_low)
        last_segment = df.iloc[start_idx:end_idx + 1]
        print('~~~~~', start_idx, end_idx)
        print(
            f"最后一段趋势起点: {last_segment.index[0]}, 终点: {last_segment.index[-1]}")

        # 高亮收盘价线（只有最后一段有值，其它为 NaN）
        highlight = pd.Series(np.nan, index=df.index)
        highlight.iloc[start_idx:end_idx +
                       1] = df['close'].iloc[start_idx:end_idx + 1]

        # swing 标记（只标记属于最后一段的 swings，显示在 high/low 上）
        swh = pd.Series(np.nan, index=df.index)
        swl = pd.Series(np.nan, index=df.index)

        swh_positions = [i for i in swing_high if i >= start_idx]
        swl_positions = [i for i in swing_low if i >= start_idx]

        for i in swh_positions:
            swh.iloc[i] = df['high'].iloc[i]   # 把点画在 high 上
        for i in swl_positions:
            swl.iloc[i] = df['low'].iloc[i]    # 把点画在 low 上

        # ---------------- make_addplot（注意：传入的 Series 与主 df index 对齐） ---------
        ap_highlight = mpf.make_addplot(
            highlight, type='line', width=1.5)    # 最后一段加粗线
        ap_swh = mpf.make_addplot(
            swh,
            type='scatter',
            markersize=60,
            marker='^')  # 上顶点
        ap_swl = mpf.make_addplot(
            swl,
            type='scatter',
            markersize=60,
            marker='v')  # 下顶点

        # ---------------- 绘图 ----------------
        mpf.plot(df,
                 type='candle',
                 style='yahoo',
                 addplot=[ap_highlight, ap_swh, ap_swl],
                 # volume=True,
                 figratio=(16, 9),
                 figscale=1.2,
                 # title = f"最后一段趋势: {df.index[start_idx]} -> {df.index[end_idx]}"
                 )

    # def marketStructure(self, df, min_points = 30):
    #     if len(df) < min_points: return False
    #     def is_trend_reversal(highs, lows, current_index):
    #         print("~~~~~~",highs,lows,current_index)
    #         # 检查是否形成更高的高点或更低的高点
    #         if current_index < 3:return False
    #         # 最近的高点和低点模式分析
    #         recent_highs = highs[current_index-2:current_index+1]
    #         recent_lows = lows[current_index-2:current_index+1]
    #         # 检查趋势转折的几种情况
    #         # 1. 高点开始降低（上升趋势结束）
    #         if (recent_highs[0] > recent_highs[1] > recent_highs[2] and
    #             recent_lows[0] > recent_lows[1] > recent_lows[2]):
    #             return True
    #         print('~~~~~1~~~')
    #         # 2. 低点开始升高（下跌趋势结束）
    #         if (recent_highs[0] < recent_highs[1] < recent_highs[2] and
    #             recent_lows[0] < recent_lows[1] < recent_lows[2]):
    #             return True
    #         print('~~~~~2~~~')
    #         # 3. 价格突破前高或前低
    #         if (highs[current_index] > max(highs[current_index-3:current_index]) or
    #             lows[current_index] < min(lows[current_index-3:current_index])):
    #             return True
    #         print('~~~~~3~~~')
    #         return False

    #     def identify_swing_points(prices, is_high=True, sensitivity=2):
    #         swing_points = []
    #         for i in range(sensitivity, len(prices) - sensitivity):
    #             if is_high:
    #                 # 识别摆动高点：中间点比左右sensitivity个点都高
    #                 if all(prices[i] > prices[i-j] for j in range(1, sensitivity+1)) and \
    #                 all(prices[i] > prices[i+j] for j in range(1, sensitivity+1)):
    #                     swing_points.append(i)
    #             else:
    #                 # 识别摆动低点：中间点比左右sensitivity个点都低
    #                 if all(prices[i] < prices[i-j] for j in range(1, sensitivity+1)) and \
    #                 all(prices[i] < prices[i+j] for j in range(1, sensitivity+1)):
    #                     swing_points.append(i)
    #         return swing_points

    #     def startPoint(df, min_swings=3):
    #         highs = df['high'].values
    #         lows = df['low'].values
    #         # 从最近的数据开始向前寻找趋势转折点
    #         for i in range(len(df) - 3, 2, -1):
    #             if is_trend_reversal(highs, lows, i):
    #                 return i
    #         return 0  # 没找到明显的转折点，从开头开始

    #     # 动态确定趋势开始点
    #     trend_start_idx = startPoint(df)
    #     print("~~start pos~~~~~", trend_start_idx)
    #     trend_data = df.iloc[trend_start_idx:].copy()
    #     # 识别摆动高点和低点
    #     high_indices = identify_swing_points(trend_data['high'].values, is_high=True, sensitivity=2)
    #     low_indices = identify_swing_points(trend_data['low'].values, is_high=False, sensitivity=2)

    #     swing_highs = []
    #     for idx in high_indices:
    #         swing_highs.append({
    #             'index': idx,
    #             'price': trend_data.iloc[idx]['high'],
    #             'time': trend_data.iloc[idx]['candle_begin_time']
    #         })

    #     swing_lows = []
    #     for idx in low_indices:
    #         swing_lows.append({
    #             'index': idx,
    #             'price': trend_data.iloc[idx]['low'],
    #             'time': trend_data.iloc[idx]['candle_begin_time']
    #         })

    #     # 分析趋势结构
    #     trend_direction = "震荡整理"
    #     trend_strength = "中性"

    #     if len(swing_highs) >= 2 and len(swing_lows) >= 2:
    #         # 检查上升趋势：更高的高点和更高的低点
    #         if (swing_highs[-1]['price'] > swing_highs[-2]['price'] and
    #             swing_lows[-1]['price'] > swing_lows[-2]['price']):
    #             trend_direction = "上升趋势"
    #             # 计算趋势强度
    #             high_change = swing_highs[-1]['price'] - swing_highs[-2]['price']
    #             low_change = swing_lows[-1]['price'] - swing_lows[-2]['price']
    #             avg_change = (high_change + low_change) / 2
    #             trend_strength = f"强势 ({avg_change:.2f})" if avg_change > 5 else f"正常 ({avg_change:.2f})"

    #         # 检查下跌趋势：更低的高点和更低的低点
    #         elif (swing_highs[-1]['price'] < swing_highs[-2]['price'] and
    #             swing_lows[-1]['price'] < swing_lows[-2]['price']):
    #             trend_direction = "下跌趋势"
    #             # 计算趋势强度
    #             high_change = swing_highs[-2]['price'] - swing_highs[-1]['price']
    #             low_change = swing_lows[-2]['price'] - swing_lows[-1]['price']
    #             avg_change = (high_change + low_change) / 2
    #             trend_strength = f"强势 ({avg_change:.2f})" if avg_change > 5 else f"正常 ({avg_change:.2f})"

    #     # 计算当前价格位置
    #     current_price = df.iloc[-1]['close']
    #     recent_high = max([h['price'] for h in swing_highs[-3:]] if swing_highs else [current_price])
    #     recent_low = min([l['price'] for l in swing_lows[-3:]] if swing_lows else [current_price])

    #     result = {
    #         'trend_direction': trend_direction,
    #         'trend_strength': trend_strength,
    #         'trend_start_time': trend_data.iloc[0]['candle_begin_time'],
    #         'analysis_period': f"{trend_data.iloc[0]['candle_begin_time']} to {df.iloc[-1]['candle_begin_time']}",
    #         'current_price': current_price,
    #         'price_position': f"{((current_price - recent_low) / (recent_high - recent_low) * 100):.1f}%" if recent_high != recent_low else "N/A",
    #         'swing_highs': swing_highs,
    #         'swing_lows': swing_lows,
    #         'data_points_used': len(trend_data)
    #     }

    #     print("=== 动态市场结构分析 ===")
    #     print(f"趋势开始时间: {result['trend_start_time']}")
    #     print(f"分析周期: {result['analysis_period']}")
    #     print(f"使用数据点: {result['data_points_used']}个K线")
    #     print(f"当前价格: {result['current_price']:.2f}")
    #     print(f"价格位置: {result['price_position']} (相对最近波动区间)")
    #     print(f"趋势方向: {result['trend_direction']}")
    #     print(f"趋势强度: {result['trend_strength']}")

    #     if result['swing_highs']:
    #         print(f"\n识别到的摆动高点 ({len(result['swing_highs'])}个):")
    #         for i, high in enumerate(result['swing_highs'][-5:]):  # 显示最近5个
    #             print(f"  高点{i+1}: {high['price']:.2f} (时间: {high['time']})")

    #     if result['swing_lows']:
    #         print(f"\n识别到的摆动低点 ({len(result['swing_lows'])}个):")
    #         for i, low in enumerate(result['swing_lows'][-5:]):  # 显示最近5个
    #             print(f"  低点{i+1}: {low['price']:.2f} (时间: {low['time']})")
    #     return result

    # 获取k线
    # def getKline(self, symbol, strStartTime, timeframe = '5m'):
    # return self.ex.getKline(symbol, [strStartTime, 'now'], timeframe =
    # timeframe)

    # 将k线数据更新到最新
    # def updateHistory(self, symbol, fileName, save = True):
    #     kLine = pdData()
    #     kLine.readFile(fileName)
    #     last = self.ex.getHistoryCandles(symbol,[kLine.get().iloc[-1]['candle_begin_time'], 'now'])
    #     kLine.pfConcat(last)
    #     if save:
    #         kLine.save2File(fileName)
    #     return kLine.get()
    # 修复k线数据

    def repairKline(self, symbol, fileName):
        return 0

    #
    def ticker(self, symbol, timeframe='5m'):  # todo:不要
        return self.ex.ticker(symbol, timeframe)
