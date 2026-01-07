import abc


class baseIndicators(metaclass=abc.ABCMeta):
    '指标基类'

    # __bindFn = None # 触发回调 todo:可以取消和signal
    # _pd = None
    #
    def __init__(self, backFn):
        # self.__bindFn = backFn
        # self._pd = pdData()
        self.init()

    def get(self, key=''):
        # return switch({'': self._pd.get()},
        #           key=key)
        # return self._pd.get()
        if self[key]:
            return self[key]

    # 发送交易信息
    # def signal(self):
        # pass

    # @abc.abstractmethod
    # def info(self): pass

    @abc.abstractmethod
    def init(self):
        pass

    @abc.abstractmethod
    def delimit(self, **kWargs):
        pass

    @abc.abstractmethod
    def calculate(self, sor_pd):
        pass
