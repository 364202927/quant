import os
import pandas as pd
import numpy as np
from datetime import timedelta, timezone
from functools import reduce
from typing import Any
from server.utils import eSampleTs
from server.utils.logger import err, log
from server.utils.fileConfig import g_config
from server.utils.common import switchFn, getFileExtension, readFile, writeFile, utc_now

# pd.set_option('display.max_rows', None)  # 最大显示行
pd.set_option('expand_frame_repr', False)  # 当列太多时不换行
pd.set_option('display.float_format', '{:.3f}'.format)  # 全局设定3位小数
# pd.set_option('mode.use_inf_as_na', True)  # 将 inf/NaN 视为缺失值

# todo:获取pf的head并转为列表
# pf.columns.tolist()
# pf.pivot_table 统计
# ffill 数值向前填充

# pd.to_datetime(pd.to_numeric(time, errors='coerce'),unit='ms') #todo时间转换
# 读取数据用iloc，写入用at

class pdData:
    "pd时间类型数据处理和格式化"
    _timeBasisAttr = 'pdData_time_basis'

    def __init__(self,head=["candle_begin_time", "open", "high", "low", "close", 'vol'], read='', style ='',data=None):#read='',xmlData=None):
        self._pf = None  # DataFrame
        self._head,self._strHead = {},{}
        self.setHead(head)
        if read != '':
            self.readFile(read)
            return
        if style != '' and data is not None:
            self.format(data, style=style)

    def setHead(self, headTab):
        index = 0
        self._strHead = {}
        for key in headTab:
            self._strHead[index] = key
            index = index + 1
        self._head = headTab

    def asType(self, tabLabel, tabType):
        for i in len(tabLabel):
            if tabType[i] == 'time':
                self._pf[tabLabel[i]] = pd.to_datetime(
                    self._pf[tabLabel[i]], unit='ms')
            else:
                self._pf[tabLabel[i]].astype(tabType[i])

    # def setPf(self, pf=None, typeKey='', dropTab=[]):
    #     # todo:bug,需要从新设headTab
    #     if pf is not None:
    #         self._pf = pf

    #     def signal():  # 信号赋值合并多空去掉重复信号  #todo:这里需要重写
    #         self._pf['signal'] = self._pf[['signal_long', 'signal_short']].sum(
    #             axis=1, min_count=1, skipna=True)
    #         temp = self._pf[self._pf['signal'].notnull()][['signal']]
    #         # 对符合条件的k线进行过滤，确保只加入开单的k线
    #         temp = temp[temp['signal'] != temp['signal'].shift(1)]
    #         self._pf['signal'] = temp['signal']
    #         self._pf.drop(['signal_long', 'signal_short'],
    #                       axis=1, inplace=True)
    #     switchFn({'signal': signal,
    #               },
    #              key=typeKey)
    #     if len(dropTab) > 0:
    #         self._pf.drop(dropTab, axis=1, inplace=True)

    # def remove(self, index):
    #     self._pf.drop(index=index, inplace=True)
        # self.kline.get().drop(['draw'], axis=1, inplace=True)

    # 初始格式化
    def format(self, dataOrTab: Any, style: str = 'candle') -> pd.DataFrame:
        def candle():  # 原始数据合并(数据类型一定是float)
            if not dataOrTab:
                self._pf = pd.DataFrame(columns=self._head)
                return
            self._pf = pd.DataFrame(dataOrTab, dtype=float)
            self._pf.rename(columns=self._strHead, inplace=True)
            # self.__pdata = self.__pdata[[kHeadIndex,'open','high','low','close','volume']]#暂时只保存以下5个值，币安得数据会多给
            # self.__pdata[kHeadIndex] = self.datetime(self.__pdata[kHeadIndex], other='ms', utc = "utc")
            self._pf[self._frist()] = pd.to_datetime(self._pf[self._frist()], unit='ms')
            self._pf.drop_duplicates(subset=[self._frist()], inplace=True) #去重
            self._pf = self._pf[self._head]

        def xml():  # 用作数据，可为任何类型
            self._pf = pd.DataFrame(dataOrTab, columns=self._head)
            if self._frist() in self._pf.columns:
                self._pf[self._frist()] = self._normalizeTime(self._pf[self._frist()])

        def concat():  # pf数据合并
            frames = [self._normalizeFrame(frame) for frame in dataOrTab]
            self._pf = pd.concat(frames, ignore_index=True)
            # print("~~~~concat~~~~~", self._pf.iloc[0].candle_begin_time,type(self._pf.iloc[0].candle_begin_time))
            # self._pf[self._frist()] = pd.to_datetime(self._pf[self._frist()], unit='ms')
            if not self._pf.empty:
                self._pf[self._frist()] = self._normalizeTime(self._pf[self._frist()])
            self._resetFormat()
            self._pf = self._pf[self._head]

        def copy():  # 复制,并重置head
            source = dataOrTab.raw() if isinstance(dataOrTab, pdData) else dataOrTab
            self._pf = self._normalizeFrame(source)
            self.setHead(self._pf.columns.tolist())

        # 格式化数据
        switchFn({'candle': candle,
                  'concat': concat,
                  'xml': xml,
                  'copy': copy},
                 key=style)
        if isinstance(self._pf, pd.DataFrame) and self._frist() in self._pf.columns:
            self._pf.attrs[self._timeBasisAttr] = 'utc'
        # self._pf.drop_duplicates(subset=[self._frist()], inplace=True) #去重
        # self._pf.dropna(subset=[self._head[1]], inplace=True)  # 去除一天都没有交易的周期
        # self._pf = self._pf[self.__pdata[self._head[5]] > 0]  # 去除成交量为0的交易周期
        return self._pf

    @staticmethod
    def _localTimezone() -> timezone:
        """Return the current local fixed offset without hard-coding a region."""
        return timezone(timedelta(hours=utc_now()))

    @classmethod
    def _normalizeTime(cls, values: Any) -> Any:
        """Normalize time values to the internal, timezone-naive UTC0 representation."""
        if isinstance(values, (int, float, np.integer, np.floating)):
            converted = pd.to_datetime(values, unit='ms', errors='coerce')
        elif isinstance(values, pd.Series) and pd.api.types.is_numeric_dtype(values):
            converted = pd.to_datetime(values, unit='ms', errors='coerce')
        else:
            converted = pd.to_datetime(values, errors='coerce')
        if isinstance(converted, pd.Timestamp):
            if converted.tzinfo is not None:
                return converted.tz_convert('UTC').tz_localize(None)
            return converted
        if isinstance(converted, pd.Series):
            if isinstance(converted.dtype, pd.DatetimeTZDtype):
                return converted.dt.tz_convert('UTC').dt.tz_localize(None)
            return converted
        if isinstance(converted, pd.DatetimeIndex) and converted.tz is not None:
            return converted.tz_convert('UTC').tz_localize(None)
        return converted

    @classmethod
    def _normalizeFrame(cls, frame: Any) -> pd.DataFrame:
        """Copy a frame and normalize its candle timestamp to UTC0."""
        result = frame.copy()
        timeKey = 'candle_begin_time'
        if isinstance(result, pd.DataFrame) and timeKey in result.columns:
            result[timeKey] = cls._normalizeTime(result[timeKey])
            result.attrs[cls._timeBasisAttr] = 'utc'
        return result

    @classmethod
    def _toLocalTime(cls, values: Any) -> Any:
        """Convert internal UTC0 values to timezone-aware local timestamps."""
        converted = cls._normalizeTime(values)
        localTz = cls._localTimezone()
        if isinstance(converted, pd.Timestamp):
            return converted.tz_localize('UTC').tz_convert(localTz)
        if isinstance(converted, pd.Series):
            return converted.dt.tz_localize('UTC').dt.tz_convert(localTz)
        return converted

    def _frist(self):
        return self._strHead[0]

    def _resetFormat(self, headFormat=False, ascending=True):  # 删除重复，并按时间排序，索引按照升序排列
        self._pf.drop_duplicates(subset=[self._frist()],keep='last', inplace=True)
        self._pf.sort_values(self._frist(), inplace=True, ascending=ascending)
        self._pf.set_index(self._frist(), inplace=True)
        self._pf.reset_index(inplace=True)
        if headFormat:
            self._pf = self._pf[self._head]
    # 内部计算使用: 返回可修改的UTC0原型
    def raw(self, cols: str | int = '', key: str = '') -> Any:
        if cols == '' and key == '':
            return self._pf
        if isinstance(cols, int) and key != '':
            return self._pf.iloc[cols][key]
        if key != '':
            return self._pf[key]
        if isinstance(cols, int):
            return self._pf.iloc[cols]

    # 对外出口: 始终返回副本，默认将UTC0时间偏移到当前时区
    def get(self, cols: str | int = '', key: str = '', offsetUtc: bool = True) -> Any:
        data = self.raw(cols, key)
        result = data.copy() if hasattr(data, 'copy') else data
        if not offsetUtc or result is None:
            return result

        timeKey = 'candle_begin_time'
        if isinstance(result, pd.DataFrame) and timeKey in result.columns:
            result[timeKey] = self._toLocalTime(result[timeKey])
            result.attrs[self._timeBasisAttr] = 'local'
        elif isinstance(result, pd.Series):
            if result.name == timeKey:
                result = self._toLocalTime(result)
                result.attrs[self._timeBasisAttr] = 'local'
            elif timeKey in result.index:
                result[timeKey] = self._toLocalTime(result[timeKey])
                result.attrs[self._timeBasisAttr] = 'local'
        elif key == timeKey:
            result = self._toLocalTime(result)
        return result

    def copy(self):
        return self._pf.copy()
    def empty(self):
        if self._pf is None:
            return True
        return len(self._pf) == 0
    def size(self):
        if self._pf is None:
            return 0
        return len(self._pf)
    def set(self, key, value, cols=''):
        if cols == '':
            self._pf[key] = value
            return
        self._pf.at[cols, key] = value
    # 截取数据段
    def getHead(self, cols):
        max_col, max_row = self._pf.shape
        if cols > max_col:
            return self._pf
        return self._pf.head(cols)
    # mpl的数据 todo:可不要
    # def getMpl(self, cols='max'):
    #     if cols == 'max':
    #         cols = len(self._pf)
    #     df = self.getHead(cols).copy()
    #     df.rename(columns={'candle_begin_time': 'dataTime',
    #                        'vol': 'volume'
    #                        }, inplace=True)
    #     df.set_index("dataTime", inplace=True)
    #     return df
    
    # 过滤
    def filter(self, *args: str):
        print("~~~~filter~~~~~", args)
        # pdResults[symbol].drop(columns =filter, inplace= True)
        col = [col for col in self._pf.columns if col.startswith(args)]
        return self._pf[col]
    

    # def show(self, typeKey=''):
    #     def showSignal():  # 统计当前的信号
    #         print('总k线:', len(self._pf))
    #         pf = self._pf[self._pf['signal'] == 1]
    #         print('做多次数：', len(pf), '\n', pf)
    #         pf = self._pf[self._pf['signal'] == -1]
    #         print('做空次数：', len(pf), '\n', pf)

    #     def other():
    #         print(self._pf, '\n')
    #     switchFn({'signal': showSignal,
    #               '': other},
    #              typeKey)

    # 从数据后面加一段数据，默认排序和去掉重复
    def pfConcat(self, pfData, reset=True):
        source = pfData.raw() if isinstance(pfData, pdData) else pfData
        frames = [frame for frame in (self._pf, source) if frame is not None]
        frames = [self._normalizeFrame(frame) for frame in frames]
        self._pf = pd.concat(frames, ignore_index=reset)
        if reset:
            self._resetFormat(True)

    # 添加一份原始数据
    def dataConcat(self, dic):
        data = dict(dic)
        if 'candle_begin_time' in data:
            data['candle_begin_time'] = self._normalizeTime(data['candle_begin_time'])
        pf = pd.DataFrame([data])
        if self._pf is None:
            self._pf = pd.DataFrame(columns=self._head)
        # self._pf = pd.concat([self._pf, pf], ignore_index=True)
        # if not pf.empty:
        #     self._pf = pd.concat([self._pf, pf], ignore_index=True)
        to_concat = [df for df in [self._pf, pf] if not df.empty and not df.isna().all().all()]
        if to_concat:
            self._pf = pd.concat(to_concat, ignore_index=True)
            if 'candle_begin_time' in self._pf.columns:
                self._pf.attrs[self._timeBasisAttr] = 'utc'

    # 左右合并
    def pfMerge(self, dataTab, key="merage"):
        frames = [self._normalizeFrame(item.raw() if isinstance(item, pdData) else item)
                  for item in dataTab]
        pf_l, pf_r = frames[0], frames[1]
        def compared():  # 左==右
            pf = pd.merge(pf_l, pf_r,
                          left_on=pf_l.columns[0],
                          right_on=pf_r.columns[0],
                          suffixes=['_left', '_right'],
                          how='left')
            return pf

        def merage():  # 根据candle_begin_time合并数据
            self._pf = reduce(lambda left,
                            right: pd.merge(left, right, on='candle_begin_time', how='inner'),
                            frames)
            self._pf.set_index(self._frist(), inplace=True)
            self._pf.reset_index(inplace=True)
            self.setHead(self._pf.columns.tolist())
            return self._pf
        # logic
        return switchFn({'compared': compared,'merage': merage},
                        key=key)

    # 重采样k线数据
    def resample(self, timeframe: str, seTime: list | None = None) -> pd.DataFrame:
        seTime = seTime or []
        if len(seTime) > 0:  # 时间段剪裁
            startTime = pd.to_datetime(seTime[0])
            endTime = pd.to_datetime(seTime[1])
            if isinstance(seTime[0], str):
                startTime -= pd.Timedelta(hours=utc_now())
            if isinstance(seTime[1], str):
                endTime -= pd.Timedelta(hours=utc_now())
            self._pf = self._pf[(self._pf[self._frist()] >= startTime) &
                                (self._pf[self._frist()] <= endTime)]
        if timeframe == '5m':
            return self._pf
        # 重采样
        if eSampleTs.get(timeframe):
            # rule = "right"
            # if timeframe == "w" or timeframe == 'm':
            #     rule = "left"
            samplePf = self._pf
            useLocalBoundary = timeframe in ('1D', '1W', '1M')
            if useLocalBoundary:
                samplePf = self._pf.copy()
                samplePf[self._frist()] += pd.Timedelta(hours=utc_now())
            self._pf = samplePf.resample(rule=eSampleTs[timeframe], on=self._frist()).agg({  # ,label=rule, closed=rule
                                                                                self._head[1]: 'first',
                                                                                self._head[2]: 'max',
                                                                                self._head[3]: 'min',
                                                                                self._head[4]: 'last',
                                                                                self._head[5]: 'sum'})
            if useLocalBoundary:
                self._pf.index -= pd.Timedelta(hours=utc_now())
        # self._pf = self._pf[self._pf['vol'] > 0]        # 去除成交量为0的交易周期
        self._pf.reset_index(inplace=True)
        return self._pf


    def save2File(self, fileName: str) -> None:
        if self._pf is None or self._pf.empty:
            # err("保存失败：", fileName, "数据为空")
            return
        totalSaved = 0
        save_pf = self._normalizeFrame(self._pf)
        path = g_config.fils('marketsPath')
        # 保存时按年份切分保存文件
        for year, yearData in save_pf.groupby(save_pf[self._frist()].dt.year):
            yearPath = os.path.join(path, str(year))
            os.makedirs(yearPath, exist_ok=True)
            fullPath = os.path.join(yearPath, fileName)
            if writeFile(yearData, fullPath):
                totalSaved += len(yearData)
                # log(f"保存到文件: {fullPath}, 数据: {len(yearData)}")
        # log(f"保存完成, 总数据: {totalSaved}")
    #fileName不需要加.parquet后续
    def readFile(self, fileName: str, isFull: bool = False) -> bool:
        path: str = g_config.fils('marketsPath')
        if not os.path.exists(path):
            return False
        # 获取有效年份目录（4位数字）
        yearDirs = sorted(
            [d for d in os.listdir(path)
             if d.isdigit() and len(d) == 4 and os.path.isdir(os.path.join(path, d))],
            reverse=True)
        if not yearDirs:
            return False
        # 非全量模式只读取最新年份
        if not isFull:
            yearDirs = yearDirs[:1]
        allData: list[pd.DataFrame] = []
        for year in yearDirs:
            filePath = os.path.join(path, year, fileName)+'.parquet' 
            if os.path.exists(filePath):
                pf = readFile(filePath)
                if pf is not None and not pf.empty:
                    allData.append(pf)
        if not allData:
            return False
        self.format(allData, style='concat')
        self.setHead(self._pf.columns.tolist())
        # log(f"读取完成: {fileName}, 共 {len(allData)} 个文件, 总数据: {len(self._pf)}")
        return True
    
    #清洗数据,range_time: [start, end]不为空检测时间范围内的缺失数据,否则检测全量异常数据  //todo不要
    def detection(self, timeFrame: str = '5m', range_time: list | None = None,
                  adjUtc: bool = True) -> list[tuple]:
        range_time = range_time or []
        def offsetUtc(timeList: list[tuple]) -> list[tuple]: #调整时间
            if not adjUtc:
                return timeList
            adjusted = []
            for tabTime in timeList:
                tb, te = tabTime
                adjusted.append((tb - pd.Timedelta(hours=1), te + pd.Timedelta(hours=1)))
            return adjusted
        # 计算时间序列的周期间隔（中位数）
        def calc_freq_delta(times: pd.Series) -> pd.Timedelta:
            if len(times) <= 1:
                return pd.Timedelta(timeFrame)
            freq_delta = times.diff().dropna().quantile(0.5)
            return freq_delta if freq_delta > pd.Timedelta(0) else pd.Timedelta(timeFrame)
        # 检测头部、中间、尾部的数据缺失区间（向量化实现）
        def detect_gaps(times: pd.Series, t_start: pd.Timestamp, t_end: pd.Timestamp,freq_delta: pd.Timedelta, threshold: pd.Timedelta) -> list[tuple]:
            missing: list[tuple] = []
            if (times.iloc[0] - t_start) > threshold:# 头部缺失
                missing.append((t_start, times.iloc[0]))
            if len(times) > 1:# 中间缺失
                gaps = times.diff()
                gap_mask = gaps > threshold
                if gap_mask.any():
                    prev_times = times.shift(1)[gap_mask]
                    curr_times = times[gap_mask]
                    missing.extend(zip(prev_times + freq_delta, curr_times))
            if (t_end - times.iloc[-1]) > threshold: # 尾部缺失
                missing.append((times.iloc[-1] + freq_delta, t_end))
            return offsetUtc(missing)
        
        #logic
        if self._pf is None or self._pf.empty:
            return []
        # 指定时间范围的缺失检测
        time_col = self._frist()
        if len(range_time) == 2:
            t_start, t_end = pd.to_datetime(range_time[0]), pd.to_datetime(range_time[1])
            if isinstance(range_time[0], str):
                t_start -= pd.Timedelta(hours=utc_now())
            if isinstance(range_time[1], str):
                t_end -= pd.Timedelta(hours=utc_now())
            times = pd.to_datetime(self._pf[time_col]).sort_values().reset_index(drop=True)
            times = times[(times >= t_start) & (times <= t_end)]
            if times.empty:
                return [(t_start, t_end)]
            freq_delta = calc_freq_delta(times)
            missing = detect_gaps(times, t_start, t_end, freq_delta, freq_delta * 10)
            return missing
        # 全量异常数据检测
        gap_tolerance = 10
        freq_delta = pd.Timedelta(timeFrame)
        df = self._pf[[time_col, 'close', 'high', 'vol']].copy()
        df = df.set_index(time_col).sort_index()
        full_idx = pd.date_range(start=df.index.min(), end=df.index.max(), freq=timeFrame)
        df = df.reindex(full_idx)
        # 标记异常：缺失或非正值
        is_bad = (df['close'].isna() | df['vol'].isna() |
                  (df['close'] <= 0) | (df['high'] <= 0))
        bad_idx = np.where(is_bad.values)[0]
        if len(bad_idx) == 0:
            return []
        # 区间合并：利用 diff 找到分割点
        gaps = np.diff(bad_idx)
        splits = np.where(gaps > gap_tolerance + 1)[0] + 1
        groups = np.split(bad_idx, splits)
        result = [(full_idx[g[0]], full_idx[g[-1]] + freq_delta) for g in groups]
        log(f"检测异常数据: {len(result)} 个区间需修复")
        return offsetUtc(result)
    
    def getIndicators(self, *args: list["baseIndicators"]):
        indPf = self._pf.copy()
        for indicator in args:
            indPf = indicator.calculateTa(indPf)
        return indPf