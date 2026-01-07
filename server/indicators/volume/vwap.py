from indicators.baseIndicators import *


class vwap(baseIndicators):
    '成交量加权平均价格'

    def info(self):
        return "\n\n~~~描述~~~ \nVWAP是一个经过成交量加权的价格平均值，常用于大型基金和机构投资者评估其交易的执行效率。\nVWAP可以用于短期的交易择时，例如当价格高于VWAP时，可能是一个卖出的好时机，反之则可能是买入的好时机。\n\n"

    def init(self):
        pass

    def delimit(self, *args):
        pass

    def calculate(self, pd):
        pass
