from server.utils.decoratorTool import singleton
from server.utils.recordBuffer import recordBuffer
from server.utils.common import readFile, writeFile, switch, dictFind

kMarketPath = "assets/markets/"
kDataPath = 'assets/config/'
kLogPath = "assets/log/"
kOrderPath = "assets/order/"
kUserType,kApiType,kStartType,kLogBufType,kOrderBufType = 'user','apiKey','start','logBuffer','orderBuffer'
kConfigPath = kDataPath+kUserType+".json"
kApikeyPath = kDataPath+kApiType+".gz"
kStartFile = kDataPath+kStartType+".json"

kBufferSize = 1000
#user.json模版
userTemp={
    "info": {
        "userName": "",
        "ccxtRetry": 0
    },
    "files": {
        "marketsPath": kMarketPath,
        "configPath": kDataPath,
    },
    "logger": {
        "_info": "",
        "outFilePath": "logs/",
    },
    "external": {
        "web": {
            "enable": 1,
            "host": "0.0.0.0",
            "port": "8000"
        },
        "console": {
            "enable": 0
        },
        "tg": {
            "enable": 0
        }
    }
}

apiTemp = {
    "market": {},
    'newsletter':{},
    'ai':{}}

# {
#     "multidQuant": [
#         "mqMain"
#     ]
# }
@singleton
class fileConfig:
    "文件配置管理器"

    def __init__(self):
        self.__userConfig = readFile(kConfigPath)
        self.__apiConfig = readFile(kApikeyPath) or apiTemp.copy()
        self.__startConfig = readFile(kStartFile) or {}
        self.__logBuf = recordBuffer(kLogPath,max_size=kBufferSize)
        self.__orderBuf = recordBuffer(kOrderPath,max_size=kBufferSize)
        # print("~~~~~~user.json~~~~~~~", self.__userConfig)
        # print("~~~~~~api.json~~~~~~~", self.__apiConfig)
        # print("~~~~~~start.json~~~~~~~", self.__startConfig)

    def setConfig(self, data: dict, configType: str | None = None):
        # from server.utils.logger import log
        def _updateUserConfig():            
            self.__userConfig = userTemp.copy()
            def setProperty(key, v):
                def findUserProperty(uKey, uV):
                    if key in uV:
                        uV[key] = v
                        return True
                    if key=='external': #强制对external字段赋值
                        for exK,exV in v.items():
                            self.__userConfig['external'][exK] = exV
                        return True
                dictFind(self.__userConfig, findUserProperty)
            dictFind(data[kUserType], setProperty)
            # print('~~~~~~user.json~~~~~', self.__userConfig)
        
        def _updateApiKeyConfig():
            self.__apiConfig = apiTemp.copy()
            def setProperty(k, v):
                if k in self.__apiConfig:
                    self.__apiConfig[k] = v
            dictFind(data[kApiType], setProperty)
            # print("~~~~~~apiKey.json~~~~~~~~",self.__apiConfig)

        def _updateStartConfig():
            self.__startConfig = data[kStartType] or {}
            # print("~~~~~~start.json~~~~~~~~",self.__startConfig)
        #logic,todo:改成switchFn
        handlers = {
            kUserType: _updateUserConfig,
            kApiType: _updateApiKeyConfig,
            kStartType: _updateStartConfig
        }
        if configType:
            handler = handlers.get(configType)
            handler(data)
            return

        # 批量处理：第一层必须是configType
        def batch(k, v):
            handler = handlers.get(k)
            if handler:
                handler()
        dictFind(data,batch)

    def get(self, configType, key=None):
        config = switch({kUserType:self.__userConfig,
                        kApiType:self.__apiConfig,
                        kStartType:self.__startConfig,
                        kLogBufType:self.__logBuf,
                        kOrderBufType:self.__orderBuf},
                        key=configType)
        if not config:
            return
        if key is None:
            return config
        return config[key]
        
    def _disposition(self, configType, key, secondKey):
        config = self.get(configType,key)
        if config.get(secondKey):
            return config[secondKey]
        return config
    
    #config数据
    def external(self, key=""):
        return self._disposition(kUserType,"external", key)
    # def logger(self, key=""):
    #     return self._disposition(kUserType,"logger", key)
    def fils(self, key=""):
        return self._disposition(kUserType,"files", key)
    def info(self, key=''):
        return self._disposition(kUserType,"info", key)
    
    #apikey
    def marketsApi(self, key=''):
        return self._disposition(kApiType,"market", key)
    def newsletterApi(self, key=''):
        return self._disposition(kApiType,"newsletter", key)
    def aiApi(self,key = ''):
        return self._disposition(kApiType, "ai", key)

    # startFile
    def startFiles(self):
        return self.__startConfig

    # # buffer
    # def logBuf(self):
    #     return self.__logBuf
    # def orderBuf(self):
    #     return self.__orderBuf

    def saveFile(self):
        if writeFile(self.__userConfig, kConfigPath):
            print('user.json保存成功')
        if writeFile(self.__apiConfig, kApikeyPath):
            print("apikey保存成功")
        if writeFile(self.__startConfig, kStartFile):
            print('start.json保存成功')
    
    def saveBuffer(self, bufType=None):
        if bufType:
            buf = switch({kLogBufType: self.__logBuf, kOrderBufType: self.__orderBuf}, key=bufType)
            if buf: buf.save2File()
        else:
            self.__logBuf.save2File()
            self.__orderBuf.save2File()

g_config = fileConfig()