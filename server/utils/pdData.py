import glob
import os
from functools import reduce
from typing import Any

import numpy as np
import pandas as pd

from server.utils import eSampleTs
from server.utils.common import switchFn, readFile as loadFile, writeFile, utc_now
from server.utils.fileConfig import g_config
from server.utils.logger import err

pd.set_option('expand_frame_repr', False)  # 当列太多时不换行
pd.set_option('display.float_format', '{:.3f}'.format)  # 全局设定3位小数

class pdData:
    "pd时间类型数据处理和格式化: 内部(raw)统一存无时区UTC0, 对外 get()/resample() 才转本地时区字符串"
    _timeKey = 'candle_begin_time'  # 外来数据表里的标准时间列名
    _extraCols = {'funding_bps': 'last'}  # head之外需要保留的列: 列名 -> resample聚合方式(资金费率取周期末生效值)

    def __init__(self, head=("candle_begin_time", "open", "high", "low", "close", "vol"),
                 read='', style='', data=None):
        self._pf = None  # DataFrame
        self._head = []
        self.setHead(head)
        if read:
            self.readFile(read)
        elif style and data is not None:
            self.format(data, style=style)

    def setHead(self, headTab):
        self._head = list(headTab)  # 拷贝: 避免共享可变默认值; 必须是list, df[tuple]会被当成单个key

    @property
    def _timeCol(self) -> str:
        return self._head[0]

    @staticmethod
    def _unwrap(obj: Any) -> Any:
        return obj.raw() if isinstance(obj, pdData) else obj

    def asType(self, tabLabel, tabType):
        for label, typ in zip(tabLabel, tabType):
            col = self._pf[label]
            self._pf[label] = self._normalizeTime(col) if typ == 'time' else col.astype(typ)

    # 初始格式化
    def format(self, dataOrTab: Any, style: str = 'candle') -> pd.DataFrame:
        def candle():  # 交易所原始k线(列名为0..n, 数据一定是float)
            if dataOrTab is None or len(dataOrTab) == 0:
                self._pf = pd.DataFrame(columns=self._head)
                return
            self._pf = pd.DataFrame(dataOrTab, dtype=float).rename(columns=dict(enumerate(self._head)))
            self._pf[self._timeCol] = self._normalizeTime(self._pf[self._timeCol])
            self._resetFormat()

        def xml():  # 用作数据,可为任何类型; 仅当含标准时间列时才转时间
            self._pf = self._normalizeFrame(pd.DataFrame(dataOrTab, columns=self._head))

        def concat():  # pf列表合并
            self._pf = pd.concat(dataOrTab, ignore_index=True)
            self._pf[self._timeCol] = self._normalizeTime(self._pf[self._timeCol])
            self._resetFormat()

        def copy():  # 复制,并重置head
            self._pf = self._normalizeFrame(self._unwrap(dataOrTab))
            self.setHead(self._pf.columns.tolist())

        switchFn({'candle': candle, 'concat': concat, 'xml': xml, 'copy': copy}, key=style)
        return self._pf

    @staticmethod
    def _normalizeTime(values: Any) -> Any:
        """统一成无时区UTC0: 数值按毫秒时间戳, 其余按 to_datetime 解析, 带时区的先转UTC"""
        isMs = (isinstance(values, (int, float, np.integer, np.floating))
                or (isinstance(values, pd.Series) and pd.api.types.is_numeric_dtype(values)))
        converted = pd.to_datetime(values, unit='ms' if isMs else None, errors='coerce', utc=True)
        if isinstance(converted, pd.Series):
            return converted.dt.tz_localize(None)
        return converted.tz_localize(None) if hasattr(converted, 'tz_localize') else converted

    @classmethod
    def _normalizeFrame(cls, frame: pd.DataFrame) -> pd.DataFrame:
        """拷贝并把 candle_begin_time 统一成UTC0"""
        result = frame.copy()
        if cls._timeKey in result.columns:
            result[cls._timeKey] = cls._normalizeTime(result[cls._timeKey])
        return result

    @classmethod
    def _toLocalTime(cls, values: Any) -> Any:
        """UTC0 -> 本地时区字符串 'YYYY-mm-dd HH:MM:SS+8' (按当前偏移的固定偏移, 不含夏令时历史)"""
        converted = cls._normalizeTime(values)
        hours = utc_now()
        offset = pd.Timedelta(hours=hours)
        if isinstance(converted, pd.Series):
            return ((converted + offset).dt.strftime('%Y-%m-%d %H:%M:%S') + f'{hours:+g}').fillna('')
        if converted is pd.NaT:
            return ''
        if isinstance(converted, pd.Timestamp):
            return f'{converted + offset:%Y-%m-%d %H:%M:%S}{hours:+g}'
        return converted

    def _resetFormat(self):
        """唯一的整理规则: 时间列为唯一键(去掉无效时间, 重复保留最新), 升序, 重置索引, 列=head+保留列"""
        t = self._timeCol
        cols = self._head + [c for c in self._extraCols if c in self._pf.columns and c not in self._head]
        self._pf = (self._pf.dropna(subset=[t]).drop_duplicates(subset=[t], keep='last')
                    .sort_values(t).reset_index(drop=True)[cols])

    # 内部计算使用: 返回可修改的UTC0原型. cols=行号(int), key=列名, 都为空返回整表
    def raw(self, cols: int | str = '', key: str = '') -> Any:
        data = self._pf if isinstance(cols, str) else self._pf.iloc[cols]
        return data[key] if key else data

    # 对外出口: 始终返回副本, 默认将UTC0时间转成本地时区字符串
    def get(self, cols: int | str = '', key: str = '', offsetUtc: bool = True) -> Any:
        data = self.raw(cols, key)
        result = data.copy() if hasattr(data, 'copy') else data
        if not offsetUtc or result is None:
            return result
        timeKey = self._timeKey
        if isinstance(result, pd.DataFrame) and timeKey in result.columns:
            result[timeKey] = self._toLocalTime(result[timeKey])
        elif isinstance(result, pd.Series) and result.name == timeKey:
            result = self._toLocalTime(result)
        elif isinstance(result, pd.Series) and timeKey in result.index:
            result[timeKey] = self._toLocalTime(result[timeKey])
        elif key == timeKey:  # 单个时间值
            result = self._toLocalTime(result)
        return result

    def copy(self):
        return self._pf.copy()

    def size(self):
        return 0 if self._pf is None else len(self._pf)

    def empty(self):
        return self.size() == 0

    def set(self, key, value, cols=''):
        if cols == '':
            self._pf[key] = value
            return
        self._pf.at[cols, key] = value

    # 截取前n行
    def getHead(self, cols):
        return self._pf.head(cols)

    # 按列名前缀过滤
    def filter(self, *prefixes: str):
        return self._pf[[c for c in self._pf.columns if c.startswith(prefixes)]]

    # 尾部追加数据. reset=True: 走 _resetFormat(按时间去重保留最新+升序+重置索引); False: 原样追加
    def pfConcat(self, pfData, reset=True):
        if self._pf is None:
            self._pf = pd.DataFrame(columns=self._head)
        frames = [self._normalizeFrame(f) for f in (self._pf, self._unwrap(pfData))
                  if f is not None and not f.empty]
        if not frames:
            return
        self._pf = pd.concat(frames, ignore_index=reset)
        if reset:
            self._resetFormat()

    # 添加一行原始数据(规则同 pfConcat: 同时间戳覆盖旧行)
    def dataConcat(self, dic):
        self.pfConcat(pd.DataFrame([dic]))

    # 左右合并. compared: 按首列左连接, 返回新表不改自身; merage: 按时间列内连接并替换自身
    def pfMerge(self, dataTab, key="merage"):
        frames = [self._normalizeFrame(self._unwrap(item)) for item in dataTab]

        def compared():
            left, right = frames[:2]
            return pd.merge(left, right, left_on=left.columns[0], right_on=right.columns[0],
                            suffixes=['_left', '_right'], how='left')

        def merge():
            self._pf = reduce(lambda left, right: pd.merge(left, right, on=self._timeKey, how='inner'), frames)
            self.setHead(self._pf.columns.tolist())
            return self._pf

        return switchFn({'compared': compared, 'merage': merge}, key=key)

    # 重采样: 不改内部数据, 返回副本. offsetUtc=True 时时间列转本地时区字符串(同get)
    # seTime=[start,end]: str按本地时区解释, 其它类型按UTC0
    def resample(self, timeframe: str, seTime: list | None = None, offsetUtc: bool = True) -> pd.DataFrame:
        t = self._timeCol
        offset = pd.Timedelta(hours=utc_now())
        pf = self._pf
        if seTime:
            start, end = [pd.to_datetime(x) - (offset if isinstance(x, str) else pd.Timedelta(0))
                          for x in seTime[:2]]
            pf = pf[pf[t].between(start, end)]

        def finish(frame):
            if offsetUtc:
                frame[t] = self._toLocalTime(frame[t])
            return frame

        if timeframe == '5m':
            return finish(pf.copy())
        rule = eSampleTs.get(timeframe)
        if not rule:
            raise ValueError(f'不支持的周期: {timeframe}')
        isLocal = timeframe in ('1D', '1W', '1M')  # 日/周/月按本地时区切分: 先平移再还原
        pf = pf.assign(**{t: pf[t] + offset}) if isLocal else pf
        o, h, lo, c, v = self._head[1:6]
        agg = {o: 'first', h: 'max', lo: 'min', c: 'last', v: 'sum'}
        agg |= {col: how for col, how in self._extraCols.items() if col in pf.columns}
        # k线以开盘时间标识、区间左闭: 必须 closed/label=left (pandas 对 W/M 默认是右闭右标签)
        sampled = pf.resample(rule, on=t, closed='left', label='left').agg(agg)
        if isLocal:
            sampled.index -= offset
        return finish(sampled.reset_index())

    # 按年份切分保存到 marketsPath/<year>/<fileName>
    def save2File(self, fileName: str) -> None:
        if self.empty():
            return
        pf = self._normalizeFrame(self._pf)
        path = g_config.fils('marketsPath')
        for year, yearData in pf.groupby(pf[self._timeCol].dt.year):
            yearPath = os.path.join(path, str(year))
            os.makedirs(yearPath, exist_ok=True)
            if not writeFile(yearData, os.path.join(yearPath, fileName)):
                err("保存失败:", year, fileName)

    # fileName不需要加.parquet后缀. 非全量只读"含该文件的最新年份"
    def readFile(self, fileName: str, isFull: bool = False) -> bool:
        pattern = os.path.join(glob.escape(g_config.fils('marketsPath')), '[0-9][0-9][0-9][0-9]',
                               glob.escape(fileName) + '.parquet')
        filePaths = sorted(glob.glob(pattern), reverse=True)
        frames = [pf for pf in map(loadFile, filePaths if isFull else filePaths[:1])
                  if pf is not None and not pf.empty]
        if not frames:
            return False
        self.format(frames, style='concat')
        return True

    def getIndicators(self, *indicators: "baseIndicators") -> pd.DataFrame:
        return reduce(lambda pf, indicator: indicator.calculateTa(pf), indicators, self._pf.copy())