from server.indicators.baseIndicators import *
import czsc
from czsc import CZSC, Freq, format_standard_kline,RawBar,Direction
from czsc.mock import generate_symbol_kines

class chanl(baseIndicators):
    '缠论'
    def init(self):
        pass

    def delimit(self, **kWargs):
        # if kWargs.get('history'): self.history = kWargs['history']
        pass
        
    def calculate(self, pd: pdData):
        return self.trend_chan(pd.raw())
    def calculateTa(self, pd):
        # print("~~~~~calculateTa~~~~~~~",pd)
        return self.trend_chan(pd)
    
    def trend_chan(self, df: pd.DataFrame, model: str = 'all') -> dict:
        """
        整合版：对历史数据进行宏观结构提取（线段/中枢），并逐根K线回放提取买卖点信号。
        
        :param df: pandas DataFrame，必须包含：candle_begin_time, open, high, low, close, vol
        :param model: 'all' (输出所有结构和信号) 或 'last' (只输出最后一段结构和最后一个信号)
        :return: dict 包含宏观结构 ('bull', 'bear', 'range') 与动态买卖点 ('buy_points', 'sell_points')
        """
        df = df.copy()
        df['candle_begin_time'] = pd.to_datetime(df['candle_begin_time'])
        
        # --- 1. 自动适应周期 (根据前两根K线的时间差) ---
        delta = df['candle_begin_time'].iloc[1] - df['candle_begin_time'].iloc[0]
        if delta >= pd.Timedelta(days=7): freq = Freq.W
        elif delta >= pd.Timedelta(days=1): freq = Freq.D
        # elif delta >= pd.Timedelta(hours=1): freq = Freq.F60
        # elif delta >= pd.Timedelta(minutes=30): freq = Freq.F30
        # elif delta >= pd.Timedelta(minutes=15): freq = Freq.F15
        # elif delta >= pd.Timedelta(minutes=5): freq = Freq.F5
        else: freq = Freq.F1

        print("~~~~~~~~date~~~~~~~~", freq)
        dt_to_idx = {row['candle_begin_time']: i for i, row in df.iterrows()}

        # --- 2. 数据转换：将 DataFrame 转为 czsc 的 RawBar 列表 ---
        bars = []
        for i, row in df.iterrows():
            bar = RawBar(
                symbol='btc', 
                id=i, 
                dt=row['candle_begin_time'],
                open=row['open'], close=row['close'], high=row['high'],low=row['low'], vol=row['vol'], 
                amount=row['vol'],  #成交额
                freq=freq)
            bars.append(bar)
        # print("~~~~~bars~~~~~~~",bars)
        
        # 3.1 动态信号抓取 (模拟实盘，逐根喂入，杜绝未来函数)
        buy_points,sell_points = [],[]
        
        # 初始化一定数量的 K 线，避免初始阶段计算报错
        # init_count = min(10, len(bars))
        # c = CZSC(bars[:init_count]) 
        
        # for bar in bars[init_count:]:
        #     c.update(bar)  # 走出一根新 K 线
            
        #     # 实时监听当下的信号字典
        #     if hasattr(c, 'signals') and c.signals:
        #         signals_str = str(c.signals)
        #         current_idx = dt_to_idx[bar.dt]
                
        #         # 捕获买卖点（将复杂的信号字典一并保留，方便后续针对性过滤，例如只抓三买）
        #         if '买' in signals_str:
        #             buy_points.append({'idx': current_idx, 'signal': c.signals.copy()})
        #         if '卖' in signals_str:
        #             sell_points.append({'idx': current_idx, 'signal': c.signals.copy()})
        c = CZSC(bars) 
        print(f"笔数量：{c.bi_list}")
        # print(f"中枢数量：{c.zs_list}")
        # print(f"线段：{c.xd_list}")
        # print(f"笔中枢：{c.bi_zs_list}")

         # --- 4. 静态结构提取（修正部分） ---
        bull, bear, ranges = [], [], []

        # 辅助函数：兼容多种中枢时间属性
        def get_zs_dt(zs, is_start=True):
            if is_start:
                return (getattr(zs, 'sdt', None) or
                        getattr(zs, 'start_dt', None) or
                        (getattr(getattr(zs, 'start', None), 'dt', None)) or
                        (getattr(getattr(zs, 'begin', None), 'dt', None)))
            else:
                return (getattr(zs, 'edt', None) or
                        getattr(zs, 'end_dt', None) or
                        (getattr(getattr(zs, 'end', None), 'dt', None)) or
                        (getattr(getattr(zs, 'stop', None), 'dt', None)))

        # 提取线段趋势
        for xd in getattr(c, 'xd_list', []):
            sdt = getattr(xd, 'sdt', None) or getattr(getattr(xd, 'start', None), 'dt', None)
            edt = getattr(xd, 'edt', None) or getattr(getattr(xd, 'end', None), 'dt', None)
            if sdt in dt_to_idx and edt in dt_to_idx:
                idx_tuple = (dt_to_idx[sdt], dt_to_idx[edt])
                if xd.direction == Direction.Up:
                    bull.append(idx_tuple)
                elif xd.direction == Direction.Down:
                    bear.append(idx_tuple)

        # 提取中枢（笔中枢 + 线段中枢）
        all_zs = getattr(c, 'bi_zs_list', []) + getattr(c, 'xd_zs_list', [])
        for zs in all_zs:
            sdt = get_zs_dt(zs, True)
            edt = get_zs_dt(zs, False)
            if sdt in dt_to_idx and edt in dt_to_idx:
                ranges.append((dt_to_idx[sdt], dt_to_idx[edt]))

        # --- 5. 结果输出 ---
        if model == 'last':
            return {
                'bull': [bull[-1]] if bull else [],
                'bear': [bear[-1]] if bear else [],
                'range': [ranges[-1]] if ranges else [],
                'buy_points': [buy_points[-1]] if buy_points else [],
                'sell_points': [sell_points[-1]] if sell_points else []
            }
        return {
            'bull': bull,
            'bear': bear,
            'range': ranges,
            'buy_points': buy_points,
            'sell_points': sell_points
        }
