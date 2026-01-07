from server.utils.decoratorTool import singleton
from server.utils.common import loadJson

kConfigPath = "assets/config/user.json"


@singleton
class fileConfig:
    __config = None

    def __init__(self):
        self.__config = loadJson(kConfigPath)
        # 检测交易所
        markets = self.markets()
        for name in markets.keys():
            if markets[name]['enable'] == 1:
                return
        print("交易所未被激活")
        # exit()

    def get(self, key=None):
        if not key:
            return self.__config
        return self.__config[key]

    def _disposition(self, key, secondKey):
        config = self.get(key)
        if config.get(secondKey):
            return config[secondKey]
        return config

    def markets(self, key=""):
        return self._disposition("market", key)

    def thirdParty(self, key=""):
        return self._disposition("thirdParty", key)

    def logger(self, key=""):
        return self._disposition("logger", key)

    def fils(self, key=""):
        return self._disposition("files", key)

    def info(self, key=''):
        return self._disposition("info", key)


g_config = fileConfig()
