from server.market import g_marketMgr
from server.utils import pdData, switchFn, switchV, slit, inRange, binanceTimestamp, err,logFormat,division,spot,str2time
from server.market.consts import *


#todo:1.现货取消挂单   ok
#todo:2.默认参数设置未生效 ok
#todo 3.交易成功单子记录
# 下单时间,策略类名,交易所名,币类型,币种,orderId,lv,方向(buy_long),委托价格price,成交价格avgPrice,总金额cumQuote, 手续费, 状态
#todo:4.交易成功后,没有更新持仓数据
#todo:5.需要把真实交易部分从baseTrade转到realTrade ok
#todo:6.读取和记录当前单子 ok

class baseTrade:
    "交易基类"

    #交易初始化        
    def settingTrade(self, **kwargs):
        self._exName = kwargs.get('exName', '')
        self._defLv = kwargs.get('def_lv', 1)
        #读取旧日志

    #现货  totelPrice总下单价, orderBook为下单方式-1为市价,(0~5)是订单本价格,price单价,exName同时在多交易所下单
    def buy(self, symbol:str, totelPrice:float|str, orderBook:int = 0, price:float|None = None, inForce = 'GTC',exName:list[str]=[]):
        self.__Trade(kBuy,spot(symbol),totelPrice,orderBook,price,False,inForce,0,exName)
    def sell(self, symbol:str, totelPrice:float|str = 'bet:100', orderBook:int = 0, price:float|None = None, inForce = 'GTC',exName:list[str]=[]):
        targets = self._exName if exName == [] else exName
        for name in targets:
            g_marketMgr.userAccount(name, True)#更新账号钱包
        self.__Trade(kSell,spot(symbol),totelPrice,orderBook,price,False,inForce,0,exName)
    def cencel(self, symbol:str, orderID = 0, exName:list[str]=[]):
        pass
    #合约
    def openLong(self, symbol:str, totelPrice:float|str, orderBook:int = 0, price:float|None = None, lv:int = 0,isMarket = False, inForce = 'GTC', exName:list[str]=[]):
        lv = self._defLv if lv == 0 else 1 
        self.__Trade(f'{kBuy}_{kLong}', symbol, totelPrice, orderBook, price,isMarket,inForce,lv, exName)
    def openShort(self, symbol:str, totelPrice:float|str, orderBook:int = 0, price:float|None = None, lv:int = 0,isMarket = False, inForce = 'GTC', exName:list[str]=[]):
        lv = self._defLv if lv == 0 else 1
        self.__Trade(f'{kSell}_{kShort}', symbol, totelPrice, orderBook, price,isMarket,inForce,lv, exName)
    # 平仓方向dir:long Short open,如忽略默认该币的仓位全卖
    def closePos(self, symbol:str, dir ='all', totelPrice:float|str = 'bet:100', orderBook:int = 0, price:float|None = None, lv:int = 0,isMarket = False, inForce = 'GTC', exName:list[str]=[]):
        pass

    def __Trade(self,stateDir:str, symbol:str, totelPrice:float|str, orderBook:int, price:float|None, isMarket:bool,inForce:str, lv:int, exName:list[str]):
        #持仓检测
        def _checkPos():
            nonlocal totelPrice
            if not isClosePos: #非平仓检测
                freeMoney = ex.accFree(category == kSpot)
                if totelPrice > freeMoney:
                    print(symbol, ":下单金额不足:", totelPrice, '余额:', freeMoney)
                    return False
                return True
            if category == kSpot:# 现货检测
                coin = newSymbol.split('/')[0]
                accCoin = ex.accFree(category == kSpot, coin)
                if accCoin == 0:
                    print(coin, ":现货账号不存在")
                    return False
                if totelPrice > accCoin: totelPrice = accCoin #最大卖出数量修正
                return True

        #跳过币本位
        category, newSymbol = slit(symbol, '_')
        if category == kDelivery:
            return
        #现货平仓标记
        isClosePos = False
        if (category == kSpot and stateDir == kSell):
            isClosePos = True
        # print("~~~~~~~~__Trade~~~~~~~~~",category, stateDir, isClosePos)
        #交易方向
        result = slit(stateDir, '_')
        state, dir = result if result else (stateDir, None)
        #多交易所处理
        targets = self._exName if exName == [] else exName
        for name in targets:
            ex = g_marketMgr.get(name)
            if not ex:
                continue
            # 总金额
            if type(totelPrice) == str:
                totelPrice = self._bet2U(ex,symbol,totelPrice,isClosePos)
            if not _checkPos():
                return
            # print("~~~__Trade~~~~~",symbol, totelPrice)#, symbolInfo)
            #最小金额修正
            _, symbolInfo = ex.coinInfo(symbol)
            costMin = symbolInfo['cost']['min'] or 0
            total = costMin if totelPrice <= costMin else totelPrice #总价<币最小交易价:按最小价下单
            #从订单本获取单价并计算数量
            orderPrice = price
            if (category != 'spot' and not price) or\
                (not price and orderBook > -1):
                orderPrice = self._BBO(ex, symbol, stateDir, orderBook) if orderBook >= 0 else None 
            amount = division(total, orderPrice, symbolInfo['step']) if orderPrice else None
            if isClosePos: #平仓
                amount = total
                total = amount * orderPrice
            # print("~~~~~__Trade send~~~~~~",state, dir, total, orderPrice, amount)
            #send
            rt = self.order(state=state,posSide=dir,symbol=symbol,ex=ex,lv=lv,totelPrice=total,amount = amount, price = orderPrice,isMarket = isMarket,inForce=inForce)

    #下单方向,币种,交易所,下单方式,委托价格,委托数量
    def order(self, state:str, symbol:str, ex:BaseException, lv:int,totelPrice:float, price:float|None, amount:float|None, isMarket:bool, inForce:str, posSide:str|None):
        pass
    
    #检查对应交易所的持仓
    def checkPos(self, exName: str):
        ex = g_marketMgr.get(exName)
        if not ex:
            return

        # 获取交易所全部持仓
        _, pos_orders = ex.findOrder(symbol='', isPos=True, isOpen=False)

        # 遍历持仓，更新 _transactionTrail
        # for pos in pos_orders:
        #     category = pos.get('category', '')
        #     symbol = pos.get('symbol', '')
        #     posSide = pos.get('positionSide', '')
        #     remainQty = float(pos.get('positionAmt', 0))

        #     key = f'{category}_{symbol}_{exName}_{posSide}'

        #     if key not in self._transactionTrail:
        #         # key 不存在，创建新条目（交易所有仓位但本地无记录）
        #         self._transactionTrail[key] = {
        #             'records': [],
        #             'remainQty': abs(remainQty),
        #             'avgPrice': float(pos.get('entryPrice', 0)),
        #             'totalCost': 0.0,
        #             'lv': int(pos.get('leverage', 1)),
        #             'openTime': str2time('strNow')}
        #     else:
        #         # 更新现有条目的持仓数量
        #         book = self._transactionTrail[key]
        #         book['remainQty'] = abs(remainQty)
        return pos_orders

    #当前挂单最优价
    def _BBO(self, ex:BaseException, symbol:str, dir:str, order:int):
        book = ex.orderBook(symbol,limit = 5)
        target = book['bids'] if dir == kBuy else book['asks']
        return target[order][0]
    # 仓位百分比转换
    def _bet2U(self,ex:BaseException,symbol:str, bet:str, isCoin:bool):
        category, newSymbol = slit(symbol, '_')
        coin = newSymbol.split('/')[0] if isCoin else ''
        # print("~~~~_bet2U~~~~~~",coin)
        freeFunds = ex.accFree(category == kSpot,coin)
        if bet.startswith("bet:"):
            proportion = int(bet[4:]) * 0.01
            return proportion * freeFunds
        return 0