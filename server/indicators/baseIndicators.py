import abc
from server.utils import pdData

class baseIndicators(metaclass=abc.ABCMeta):
    '指标基类'

    def __init__(self):
        self._pd = pdData()
        # self._isTa = False  # 是否使用ta库计算
        self.init()

    # def get(self, key=''):
    #     # return switch({'': self._pd.get()},
    #     #           key=key)
    #     # return self._pd.get()
    #     if self[key]:
    #         return self[key]
    @abc.abstractmethod
    def init(self):pass
    @abc.abstractmethod
    def delimit(self, **kWargs):pass #指标参数设置
    @abc.abstractmethod
    def calculate(self, pd:pdData):pass
    @abc.abstractmethod
    def calculateTa(self, pd:pdData):pass
