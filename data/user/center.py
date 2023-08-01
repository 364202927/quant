from include import *

@singleton
class userCenter:
    '用户记录'

    accountBooks = {}

    # 添加交易所记录
    def initRecord(self, objEx):
        # todo:记录交易所的逻辑
        # logFormat(objEx.account())
        pass
    
    #更新交易所数据
    def update():
        pass

g_userCenter = userCenter()