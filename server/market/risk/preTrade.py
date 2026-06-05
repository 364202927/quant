import asyncio
from server.utils import evtConnect, evtFireAsync, kEvt_Market, kEvt_Engine, extInterface, log
from server.market import eMarketId


class preTrade:
    """事前风控：限额/价格偏离/黑名单，通过则转发 omsOrder"""

    def __init__(self):
        # super().__init__()
        evtConnect(kEvt_Market, self)

    def evtProcess(self, key, *args):
        # if len(args) < 4 or args[0] != eMarketId['sOrder']:
        #     return
        # _, taskName, exName, params = args[0], args[1], args[2], args[3]
        # if self._check(taskName, params):
        #     asyncio.ensure_future(
        #         evtFireAsync(kEvt_Market, eMarketId['omsOrder'], taskName, exName, params)
        #     )
        pass

    def _check(self, taskName: str, params: dict) -> bool:
        config = self._riskConfig(taskName)
        if not config:
            return True
        symbol = params.get('symbol', '')
        if symbol in config.get('blacklist', []):
            log(f"[preTrade] {symbol} 在黑名单，拒绝")
            return False
        max_amount = config.get('maxOrderAmount')
        if max_amount and params.get('amount', 0) > max_amount:
            log(f"[preTrade] {symbol} 订单量超限 {params['amount']} > {max_amount}，拒绝")
            return False
        max_dev = config.get('maxPriceDeviation', 0)
        if max_dev and params.get('price') and params.get('refPrice'):
            dev = abs(params['price'] - params['refPrice']) / params['refPrice']
            if dev > max_dev:
                log(f"[preTrade] {symbol} 价格偏离 {dev:.2%} > {max_dev:.2%}，拒绝")
                return False
        return True

    def _riskConfig(self, taskName: str) -> dict:
        # return evtQuery(kEvt_Engine, eEngineId['getRiskConfig'], taskName) or {}
        pass

    # async def run(self) -> None:
    #     while True:
    #         await asyncio.sleep(3600)
