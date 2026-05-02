from server.strategy.base.baseTrade import *
from server.utils import slit
# todo:冷静期
# todo:默认风险管理,例如设定止损下限，每天交易次数，杠杆控制


class realTrade(baseTrade):
    "真实交易"
    
    #现货
    def buy(self, symbol:str, totelPrice:float|str, orderBook:int = 0, price:float|None = None, inForce = 'GTC',exName:list[str]=[]):
        super().buy(symbol,totelPrice,orderBook,price,inForce,exName)
    def sell(self, symbol:str, totelPrice:float|str = 'bet:100', orderBook:int = 0, price:float|None = None, inForce = 'GTC',exName:list[str]=[]):
        super().sell(symbol,totelPrice,orderBook,price,inForce,exName)
    def cencel(self, symbol:str, orderID = 0, exName:list[str]=[]):
        targets = self._exName if exName == [] else exName
        for name in targets:
            ex = g_marketMgr.get(name)
            if not ex:
                continue
            symbol = spot(symbol)
            rtOrder = ex.findOrder(symbol, orderID) #查找所有现货挂单
            for open in rtOrder:
                rt = ex.order('cancel', symbol, open['orderId'],0)
    # 合约
    def openLong(self, symbol:str, totelPrice:float|str, orderBook:int = 0, price:float|None = None, lv:int = 0,isMarket = False, inForce = 'GTC', exName:list[str]=[]):
        super().openLong(symbol,totelPrice,orderBook,price,lv,isMarket,inForce,exName)
    def openShort(self, symbol:str, totelPrice:float|str, orderBook:int = 0, price:float|None = None, lv:int = 0,isMarket = False, inForce = 'GTC', exName:list[str]=[]):
        super().openShort(symbol,totelPrice,orderBook,price,lv,isMarket,inForce,exName)
    def closePos(self, symbol:str, dir ='all', totelPrice:float|str = 'bet:100', orderBook:int = 0, price:float|None = None, lv:int = 0,isMarket = False, inForce = 'GTC', exName:list[str]=[]):
        isOpen = dir == 'open' or dir == 'all'                  #挂单
        isPos = dir == kLong or dir == kShort or dir == 'all'   #持仓
        lv = self._defLv if lv == 0 else 1
        # print('~~~closePos~~~~~',isOpen,isPos,self.__exName)
        targets = self._exName if exName == [] else exName
        for name in targets:
            ex = g_marketMgr.get(name)
            if not ex:
                continue
            rtOpen, rtOrder = ex.findOrder(symbol=symbol, isPos=isPos, isOpen=isOpen)
            if dir != 'all' and len(rtOrder) > 0: #过滤
                rtOrder = [order for order in rtOrder if order['positionSide'] == dir]
            #取消挂单
            for open in rtOpen:
                rt = ex.order('cancel', symbol, open['orderId'],0)
            #平仓
            state = {kShort:kBuy,kLong:kSell}
            if totelPrice.startswith("bet:"):
                proportion = int(totelPrice[4:]) * 0.01
            for order in rtOrder:
                # {'symbol': 'DOGEUSDT', 'positionAmt': '-53.0', 'entryPrice': '0.09522', 'markPrice': '0.09343648', 'unRealizedProfit': '0.09452656', 'liquidationPrice': '32.03850263', 
                #  'leverage': '1', 'positionSide': 'SHORT', 'updateTime': '1772197402977', 'maxNotionalValue': '200000000', 'notional': '-4.95213344', 'breakEvenPrice': '0.09517239'}
                pos = order.get('positionSide')
                amt = abs(float(order.get('positionAmt')))
                # ent = float(order.get('entryPrice')) #买入价
                if totelPrice.startswith("bet:"):
                    proportion = int(totelPrice[4:]) * 0.01
                    amt = amt*proportion
                rt = self.order(state[pos], symbol, name, lv, 0, self._BBO(ex, symbol, state[pos], orderBook), amt, isMarket, inForce, pos)

    #下单方向,币种,交易所,下单方式,委托价格,委托数量
    def order(self, state:str, symbol:str, ex, lv:int, totelPrice:float, price:float|None, amount:float|None, isMarket:bool, inForce:str, posSide:str|None):
        category, _ = slit(symbol, '_')
        exName = ex.get('title')
        dir_str = f'{state}_{posSide}' if posSide else state
        # 1. 创建记录
        uid = self.record(exName=exName, category=category, symbol=symbol,
                          orderId='', lv=lv, dir=dir_str,
                          orderPrice=price or 0)
        # 2. 下单
        rt = ex.order(state=state, symbol=symbol, totelPrice=totelPrice,
                      price=price, amount=amount, lv=lv,
                      isMarket=isMarket, inForce=inForce, posSide=posSide)
        if not rt:
            return None
        # 3. 更新记录
        self.updateRecord(uid,
                          avgPrice=float(rt.get('avgPrice', 0)),
                          origQty=float(rt.get('origQty', 0)),
                          cumQuote=float(rt.get('cumQuote', 0)),
                          fee=float(rt.get('fee', 0)),
                          orderId=str(rt.get('orderId', '')))
        return uid
