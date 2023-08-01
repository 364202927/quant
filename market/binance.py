from market.baseExchange import *


class binance(baseExchange):
    _name = "币安"

    def __init__(self, description):
        super().__init__(description)
        # class_name = type(self).__name__
        # print(class_name)
