# import asyncio
from server.utils import evtConnect, evtFireAsync, kEvt_Market,switchFn,logFormat
from server.market import eMarketId


class storageCenter:
    "交易所个人资产数据缓存"

    def __init__(self):
        self.__snapshot: dict[str, dict] = {}  # {okx: {'main': {},... },bybit:{'xx':{}},...}
        evtConnect(kEvt_Market, self)

    def evtProcess(self, key, *args):
        id, exName = args[0], args[1]
        def _balanceUpdata(exName,key,data):
            self.__snapshot.setdefault(exName, {}).setdefault(key, {}).update(data)
            print("~~~~updata balance~~~~~~~~")
            logFormat(self.__snapshot)
        #evt事件
        def _balance():
            key, data = args[2],args[3]
            _balanceUpdata(exName, key, data)
        def _increment():
            key, data = args[2],args[3]
            _balanceUpdata(exName, key, data)
        switchFn({eMarketId['balance']: _balance,
                  eMarketId['wsBalance']: _increment,
                  }, key=id)

    

    # def position(self, exName: str = '') -> dict:
    #     if exName:
    #         return self._snapshot.get(exName, {}).get('position', {})
    #     return {ex: d.get('position', {}) for ex, d in self._snapshot.items()}

 

    # def _onPosition(self, exName: str, positions: list):
    #     pos = {p['symbol']: p for p in positions if float(p.get('contracts', 0)) != 0}
    #     prev = self._snapshot.setdefault(exName, {}).get('position', {})
    #     self._snapshot.setdefault(exName, {})['position'] = pos
    #     if pos != prev:
    #         import asyncio
    #         asyncio.ensure_future(
    #             evtFireAsync(kEvt_Market, eMarketId['iHolding'], exName, 'position', pos, prev)
    #         )