from server.utils import switch, evtConnect, evtFire, eTaskState, kEvt_GetTime, kEvt_Time, time2ID
# from data.user.center import g_userCenter
# from data.user.shareDate import g_share

# todo:初次进程序读取上次任务
# todo:当下单成功时，修改状态为run
# todo:关闭任务，改变时间等还没完成


class task:
    __shared = {}  # task间信息互传的类

    def __init__(self, fnCta):
        self.info = ''
        self.tacticsTime = []           # 触发时间
        self.__id = time2ID()                   # 任务id
        self.__state = eTaskState.get("eActive")# 当前状态
        self.__fnCta = fnCta
        self.indicators = {}  # 绑定的策略{name:class,name2:class2}
        
        evtConnect(kEvt_GetTime, self)
        # evtConnect(kEvt_Signal, self)

    def info(self, strInfo):
        self.info = strInfo

    def get(self, key=''):
        return switch({'': self.tacticsTime,
                       'id': self.__id,
                       # 'order':self.taskOrder,
                       'className': self.__class__.__name__,
                    #    'symbols': self.symbols,
                       'info': self.info,
                       'name': self.__doc__,
                       'indicators': self.indicators,
                       'store': self.__shared},
                      key=key)

    # 切换任务状态
    def state(self):
        return self.__state
    # 激活任务
    def active(self):
        if self.state() > eTaskState.get("eActive"):
            return
        self.__state = eTaskState.get("eWait")
        # 判断第一次激活，向定时器注册任务
        if len(self.indicators) == 0 and \
                len(self.tacticsTime) == 0:
            self._register()
    def pause(self):
        pass
    
    def regTime(self, *timeKeys):
        self.tacticsTime = list(timeKeys) if timeKeys else []
    
    # 关闭任务 todo
    def close(self):
        # if self.state() == eTaskState.get("eWait") or \
        # 	self.state() == eTaskState.get("eSell"):
        # 	self.__state = eTaskState.get("eActive")
        # 	print("~~todo关掉任务后把任务信息删掉~~~")
        # elif self.state() == eTaskState.get("eRun"):
        # 	self.__state = eTaskState.get("eSell")

        # elif self.state() == eTaskState.get("eSell"):
        # 	self.__state = eTaskState.get("eSell")
        pass

    # def addStrategy(self, strTactics):
    # 	strategy = require('strategy.' + strTactics)(self.__ex, self.__name)
    # 	self.__strategys.append(strategy)
        # self.regStrategy(strategy)

    # def delStrategy(self, strTactics):
    # 	pass
    # def clear(self, strTactics):
    # 	pass

    # 注册时间，策略
    def _register(self):
        # g_share.regSymbols(self.__ex, strategy.symbol) #公用资源添加监控的币种
        # g_userCenter.addTask(self)						#个人中心添加任务
        self.init()
        if len(self.tacticsTime) > 0:
            evtFire(kEvt_Time, self.get('id'), self.get())  # 告诉定时器任务id和触发间隔
    
    # 处理共享数据
    def store(self, key, value):
        self.__shared[key] = value

    def take(self, key=''):
        shared = self.get("store")
        if key == '':
            return shared
        return shared[key]

    def getCTA(self, name=''):
        rtCta = self.__fnCta(name)
        return rtCta
    # 继承
    # def init(self):初始化
    # def evtSignal(self, indicatorsName):信号
    # def evtTime(self):时间
