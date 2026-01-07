import pandas as pd
from functools import reduce
from server.utils.common import switchFn, joinPath, getFileExtension
from server.utils.fileConfig import g_config
from server.utils.logger import err, log
from server.utils import eSampleTs

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
    "pd数据处理和格式化"
    _pf = None  # DataFrame
    # 默认k线头部
    _head = {}
    _strHead = {}

    def __init__(
        self,
        head=["candle_begin_time", "open", "high", "low", "close", 'vol'],
        read='',
        xmlData=None
    ):
        self.setHead(head)
        if xmlData is not None:
            self.format(xmlData, style="xml")
        if read != '':
            self.readFile(read)

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

    def setPf(self, pf=None, typeKey='', dropTab=[]):
        # todo:bug,需要从新设headTab
        if pf is not None:
            self._pf = pf

        def signal():  # 信号赋值合并多空去掉重复信号  #todo:这里需要重写
            self._pf['signal'] = self._pf[['signal_long', 'signal_short']].sum(
                axis=1, min_count=1, skipna=True)
            temp = self._pf[self._pf['signal'].notnull()][['signal']]
            # 对符合条件的k线进行过滤，确保只加入开单的k线
            temp = temp[temp['signal'] != temp['signal'].shift(1)]
            self._pf['signal'] = temp['signal']
            self._pf.drop(['signal_long', 'signal_short'],
                          axis=1, inplace=True)
        switchFn({'signal': signal,
                  },
                 key=typeKey)
        if len(dropTab) > 0:
            self._pf.drop(dropTab, axis=1, inplace=True)

    def remove(self, index):
        self._pf.drop(index=index, inplace=True)
        # self.kline.get().drop(['draw'], axis=1, inplace=True)

    # 初始格式化
    def format(self, dataOrTab, style='candle', utc=0):
        def candle():  # 原始数据合并(数据类型一定是float)
            self._pf = pd.DataFrame(dataOrTab, dtype=float)
            self._pf.rename(columns=self._strHead, inplace=True)
            # self.__pdata = self.__pdata[[kHeadIndex,'open','high','low','close','volume']]#暂时只保存以下5个值，币安得数据会多给
            # self.__pdata[kHeadIndex] = self.datetime(self.__pdata[kHeadIndex], other='ms', utc = "utc")
            self._pf[self._frist()] = pd.to_datetime(
                self._pf[self._frist()], unit='ms')
            self._pf = self._pf[self._head]

        def xml():  # 用作数据，可为任何类型
            self._pf = pd.DataFrame(dataOrTab, columns=self._head)

        def concat():  # pf数据合并
            self._pf = pd.concat(dataOrTab, ignore_index=True)
            self._resetFormat()
            self._pf = self._pf[self._head]

        def copy():  # 复制,并重置head
            self._pf = dataOrTab.copy()
            self.setHead(self._pf.columns.tolist())

        # 格式化数据
        switchFn({'candle': candle,
                  'concat': concat,
                  'xml': xml,
                  'copy': copy},
                 key=style)
        # 转换为当前utc时间
        if utc > 0:
            self._pf[self._frist()] += pd.Timedelta(hours=utc)
        # self._pf.drop_duplicates(subset=[self._frist()], inplace=True) #去重
        # self._pf.dropna(subset=[self._head[1]], inplace=True)  # 去除一天都没有交易的周期
        # self._pf = self._pf[self.__pdata[self._head[5]] > 0]  # 去除成交量为0的交易周期
        return self._pf

    def _frist(self):
        return self._strHead[0]

    def _resetFormat(self, headFormat=False, ascending=True):  # 删除重复，并按时间排序，索引按照升序排列
        self._pf.drop_duplicates(
            subset=[
                self._frist()],
            keep='last',
            inplace=True)
        self._pf.sort_values(self._frist(), inplace=True, ascending=ascending)
        self._pf.set_index(self._frist(), inplace=True)
        self._pf.reset_index(inplace=True)
        if headFormat:
            self._pf = self._pf[self._head]
    # 返回index的数据

    def get(self, cols='', key=''):
        # print("~~get~~~",cols,key)
        if cols == '' and key == '':
            # print("~~~a~~~")
            return self._pf
        # elif cols >= 0 and key >= 0:
        if isinstance(cols, int) and isinstance(key, int):
            # print("~~~b~~~")
            return self._pf.iloc[cols][key]
        elif key != '':
            # print("~~~c~~~")
            return self._pf[key]
        # elif cols != '':
        if isinstance(cols, int):
            # print("~~~d~~~")
            return self._pf.iloc[cols]

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
        else:
            self._pf.at[cols, key] = value
    # 截取数据段

    def getHead(self, cols):
        max_col, max_row = self._pf.shape
        if cols > max_col:
            return self._pf
        return self._pf.head(cols)
    # mpl的数据

    def getMpl(self, cols='max'):
        if cols == 'max':
            cols = len(self._pf)
        df = self.getHead(cols).copy()
        df.rename(columns={'candle_begin_time': 'dataTime',
                           'vol': 'volume'
                           }, inplace=True)
        df.set_index("dataTime", inplace=True)
        return df
    # 根本标签进行过滤

    def filter(self, *args: str):
        col = [col for col in self._pf.columns if col.startswith(args)]
        return self._pf[col]

    def show(self, typeKey=''):
        def showSignal():  # 统计当前的信号
            print('总k线:', len(self._pf))
            pf = self._pf[self._pf['signal'] == 1]
            print('做多次数：', len(pf), '\n', pf)
            pf = self._pf[self._pf['signal'] == -1]
            print('做空次数：', len(pf), '\n', pf)

        def other():
            print(self._pf, '\n')
        switchFn({'signal': showSignal,
                  '': other},
                 typeKey)

    # 从数据后面加一段数据，默认排序和去掉重复
    def pfConcat(self, pfData, reset=True):
        self._pf = pd.concat([self._pf, pfData], ignore_index=reset)
        if reset:
            self._resetFormat(True)

    # 添加一份原始数据
    def dataConcat(self, dic):
        pf = pd.DataFrame([dic])
        if self._pf is None:
            self._pf = pd.DataFrame(columns=self._head)
        self._pf = pd.concat([self._pf, pf], ignore_index=True)

    # 左右合并
    def pfMerge(self, dataTab, key="merage"):
        pf_l, pf_r = dataTab[0].copy(), dataTab[1].copy()

        def compared():  # 左==右
            pf = pd.merge(pf_l, pf_r,
                          left_on=pf_l.columns[0],
                          right_on=pf_r.columns[0],
                          suffixes=['_left', '_right'],
                          how='left')
            return pf

        def merage():  # 根据candle_begin_time合并数据
            self._pf = reduce(
                lambda left,
                right: pd.merge(
                    left,
                    right,
                    on='candle_begin_time',
                    how='inner'),
                dataTab)
            self._pf.set_index(self._frist(), inplace=True)
            self._pf.reset_index(inplace=True)
            self.setHead(self._pf.columns.tolist())
            return self._pf
        # logic
        return switchFn({'compared': compared,
                        'merage': merage},
                        key=key)

    # 从采样，改变时间粒度
    def resample(self, timeframe, seTime=[]):
        if len(seTime) > 0:  # 时间段剪裁
            self._pf = self._pf[(self._pf[self._frist()] >= seTime[0]) &
                                (self._pf[self._frist()] <= seTime[1])]
        # 重采样
        if eSampleTs.get(timeframe):
            # rule = "right"
            # if timeframe == "w" or timeframe == 'm':
            #     rule = "left"
            self._pf = self._pf.resample(rule=eSampleTs[timeframe], on=self._frist()).agg(  # ,label=rule, closed=rule
                {self._head[1]: 'first',
                 self._head[2]: 'max',
                 self._head[3]: 'min',
                 self._head[4]: 'last',
                 self._head[5]: 'sum'})
        self._pf = self._pf[self._pf['vol'] > 0]        # 去除成交量为0的交易周期
        self._pf.reset_index(inplace=True)
        return self._pf

    # 保存文件
    def save2File(self, fileName, path=g_config.fils('marketsPath')):
        if self._pf.shape[0] == 0:
            err("保存失败：", fileName, "数据：", self._pf.shape[0])
            return
        fileType, _ = getFileExtension(fileName)
        fullPath = joinPath(path, fileName)
        if fileType == 'csv':
            self._pf.to_csv(fullPath, index=False)
        elif fileType == 'pkl':
            self._pf.to_pickle(fullPath)
        else:
            err("未支持保存此文件", fileName)
            return
        log("保存到文件：", fullPath, "数据：", self._pf.shape[0])
    # 读取文件

    def readFile(self, fileName, path=g_config.fils('marketsPath')):
        fileType, _ = getFileExtension(fileName)
        fullPath = joinPath(path, fileName)
        try:
            if fileType == 'csv':
                self._pf = pd.read_csv(filepath_or_buffer=fullPath,
                                       encoding='gbk',
                                       parse_dates=[self._frist()])
            elif fileType == 'pkl':
                self._pf = pd.read_pickle(fullPath)
        except Exception as ex:
            return False
        #
        self.setHead(self._pf.columns.tolist())
        self._pf.drop_duplicates(subset=[self._frist()], inplace=True)  # 去重
        # self._pf.dropna(subset=[self._head[1]], inplace=True)  # 去除一天都没有交易的周期
        errpf = self._pf[self._pf['vol'] <= 0]
        if errpf.shape[0] > 0:
            print("vol数据存在错误或缺失:")
            # print(errpf)
            print('\n')

        # self._pf = self._pf[self._pf['vol'] > 0]        #todo: 去除成交量为0的交易周期
        self._pf[self._frist()] = pd.to_datetime(
            self._pf[self._frist()], unit='ms')
        self._pf.reset_index(inplace=True, drop=True)  # 重置索引
        return True
