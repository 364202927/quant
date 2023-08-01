from include import *
import pandas as pd

# pd.set_option('display.max_rows', None) #最大显示行
pd.set_option('expand_frame_repr', False)  # 当列太多时不换行

class pdData:
    "pd数据处理和格式化"
    _pf = None          # DataFrame
    #默认k线头部
    _head = ["candle_begin_time", "open", "high", "low", "close", 'vol']
    _strHead = {}
    def __init__(self):
        self.setHead(self._head)

    def setHead(self, headTab):
        index = 0
        self._strHead = {}
        for key in headTab:
            self._strHead[index] = key
            index = index +1
        self._head = headTab

    def format(self, dataOrTab, utc = 0):
        def candle():#isFormat = True):
            # if isFormat:
            self._pf = pd.DataFrame(dataOrTab, dtype=float)
            self._pf.rename(columns = self._strHead, inplace=True)
			# self.__pdata = self.__pdata[[kHeadIndex,'open','high','low','close','volume']]#暂时只保存以下5个值，币安得数据会多给
			# self.__pdata[kHeadIndex] = self.datetime(self.__pdata[kHeadIndex], other='ms', utc = "utc")
            self._pf[self._fristKey()] = pd.to_datetime(self._pf[self._fristKey()], unit='ms')
            # return True

        def concat():
            self._pf = pd.concat(dataOrTab, ignore_index=True)
            # 删除重复，并按时间排序，索引按照升序排列
            self._pf.drop_duplicates(subset=[self._fristKey()], keep='last', inplace=True)
            self._pf.sort_values(self._fristKey(), inplace=True)
            self._pf.set_index(self._fristKey(), inplace=True)
            self._pf.reset_index(inplace=True)
        #是否tab
        if isinstance(dataOrTab[0], pd.DataFrame):
            concat()
        else:
            candle()
        # 只保留头部需要的
        self._pf = self._pf[self._head]
        if utc > 0: #转换为当前utc时间
            self._pf[self._fristKey()] += pd.Timedelta(hours = utc)
        # self._pf.dropna(subset=[self._head[1]], inplace=True)  # 去除一天都没有交易的周期
        # self._pf = self._pf[self.__pdata[self._head[5]] > 0]  # 去除成交量为0的交易周期
        return self._pf

    def _fristKey(self):
        return self._strHead[0]
    def get(self, rowKey = '', colKey = ''):
        if rowKey == '' or colKey == '':
            return self._pf
        return self._pf.iloc[rowKey, colKey]
    def show(self):
        print(self._pf)
        
    # 从k线数据后面加一段数据
    def concat(self, data):
        pass
    # 左==右    
    def merge(self, leftData, rightData):
        pass
    #从设pf
    def resample(self, timeframe, seTime = []):
        if len(seTime) > 0:# 时间段剪裁
            self._pf = self._pf[(self._pf[self._fristKey()].dt.date >= pd.to_datetime(seTime[0]).date()) &
                                (self._pf[self._fristKey()].dt.date < pd.to_datetime(seTime[1]).date())]
        if sampleTs.get(timeframe): #重采样
            rule = "right"
            if timeframe == "w" or timeframe == 'm':
                rule = "left"
            self._pf = self._pf.resample(rule = sampleTs[timeframe],on=self._head[0],label=rule, closed=rule).agg(
                                        {self._head[1]: 'first',
                                        self._head[2]: 'max', 
                                        self._head[3]: 'min', 
                                        self._head[4]: 'last', 
                                        self._head[5]: 'sum'})
        self._pf.reset_index(inplace=True)
        return self._pf

    # def resample(self, startTime, stopTime):
        # self.__pdata[(self.__pdata[kHeadIndex].dt.date >= self.datetime(args[0]).date()) &
        #             (self.__pdata[kHeadIndex].dt.date < self.datetime(args[1]).date())]
        # pass

    #todo:记录时检测
    def save2File(self, fileName, covered = False):
        if self._pf.shape[0] == 0:
            err("保存失败：",fileName, "数据：", self._pf.shape[0])
            return
        # todo:检测路径下是否存在文件，若存在提醒

        fileType = getFileExtension(fileName)
        fullPath = joinPath(g_config.fils('marketsPath'), fileName)
        # print("~~~~~fileType~~~~~",fileType)
        if fileType == 'csv':
            self._pf.to_csv(fullPath, index=False)
        elif fileType == 'pkl':
            self._pf.to_pickle(fullPath)
        else:
            err("未支持保存此文件",fileName)
            return
        log("保存到文件：",fullPath, "数据：", self._pf.shape[0])

    def readFile(self, fileName):
        fileType = getFileExtension(fileName)
        fullPath = joinPath(g_config.fils('marketsPath'), fileName)
        if fileType == 'csv':
            self._pf = pd.read_csv(filepath_or_buffer = fullPath,
										encoding='gbk',
										parse_dates=[self._fristKey()])
        elif fileType == 'pkl':
            self._pf = pd.read_pickle(fullPath)
            pass
        else:
            err("读取失败:",fileName)
            return
        self._pf.drop_duplicates(subset=[self._fristKey()], inplace=True) #去重
        self._pf.reset_index(inplace=True, drop=True) #重置索引