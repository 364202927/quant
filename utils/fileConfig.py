from utils.decoratorTool import singleton
from utils.common import *

@singleton
class fileConfig:
    __config = None

    def __init__(self):
        self.__config = loadJson("config.json")

        # 检测交易所配置
        abnormal = False
        markets = self.markets()
        for name in markets.keys():
            if markets[name]['enable'] == 1:
                abnormal = True
        if not abnormal:
            print("err:所有交易所未激活")
    
    def _get(self, key):
        return self.__config[key]
    def _disposition(self, key, secondKey):
        config = self._get(key)
        if config.get(secondKey):
            return config[secondKey]
        return config

    def markets(self, key = ""):
        return self._disposition("market", key)
    def thirdParty(self,key = ""):
        return self._disposition("thirdParty", key)
    def logger(self, key = ""):
        return self._disposition("logger", key)    
    def fils(self, key = ""):
        return self._disposition("files", key)

g_config = fileConfig()
