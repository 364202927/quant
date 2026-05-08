import abc,talib
import numpy as np
import pandas as pd
from server.utils import pdData,logFormat,logJson
from server.utils.science import *

class baseIndicators(metaclass=abc.ABCMeta):
    '指标基类'

    def __init__(self):
        self._pd = pdData()
        self.init()

    @abc.abstractmethod
    def init(self):pass
    @abc.abstractmethod
    def delimit(self, **kWargs):pass #指标参数设置
    @abc.abstractmethod
    def calculate(self, pd:pdData):pass
    @abc.abstractmethod
    def calculateTa(self, pd:pdData):pass
