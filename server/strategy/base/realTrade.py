from server.strategy.base.baseTrade import *
# todo:冷静期
# todo:默认风险管理,例如设定止损下限，每天交易次数，杠杆控制


class realTrade(baseTrade):
    "真实交易"
    
    #现货订单取消
    def cencel(self, symbol:str, orderID = 0, exName:list[str]=[]):
        targets = self._exName if exName == [] else exName
        for name in targets:
            ex = g_marketMgr.get(name)
            if not ex:
                continue
            symbol = spot(symbol)
            rtOrder = ex.findOrder(symbol, orderID) #查找所有现货挂单
            print('~~~~order~~~~',rtOrder)
            for open in rtOrder:
                rt = ex.order('cancel', symbol, open['orderId'],0)
                print("~~~~~~~~cancal~~~~~~~~",rt)
    # 合约平仓 
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
            print("~~~~~~~~仓位查询~~~~~~~", rtOpen, rtOrder)
            #取消挂单
            for open in rtOpen:
                rt = ex.order('cancel', symbol, open['orderId'],0)
                print("~~~~~~~~cancal~~~~~~~~",rt)
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
                print("~~~~~~~~平仓~~~~~~~~",rt)

    #下单方向,币种,交易所,下单方式,委托价格,委托数量
    def order(self, state:str, symbol:str, ex:BaseException, lv:int,totelPrice:float, price:float|None, amount:float|None, isMarket:bool, inForce:str, posSide:str|None):
        print("~~~~~ send~~~~~~",state, posSide, totelPrice, price, amount)
        return ex.order(state = state, symbol=symbol, totelPrice = totelPrice, price = price, amount=amount, lv=lv, isMarket = isMarket, inForce = inForce, posSide=posSide)
