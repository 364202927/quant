import asyncio
from server.utils import evtConnect, evtFireAsync, kEvt_Market, extInterface
from server.market import eMarketId


class storageCenter:
    """监听交易所余额/持仓变动，差量触发 iHolding"""

    def __init__(self):
        super().__init__()
        self._snapshot: dict[str, dict] = {}  # {exName: {'balance': {}, 'position': {}}}
        evtConnect(kEvt_Market, self)

    def seed(self, exName: str, acc: dict) -> None:
        """用REST账户数据预填充余额快照，避免WS首次推送前余额为空"""
        free = {c: float(v) for c, v in acc.get('free', {}).items() if v and float(v) > 0}
        self._snapshot.setdefault(exName, {})['balance'] = free

    def balance(self, exName: str = '') -> dict:
        if exName:
            return self._snapshot.get(exName, {}).get('balance', {})
        return {ex: d.get('balance', {}) for ex, d in self._snapshot.items()}

    def position(self, exName: str = '') -> dict:
        if exName:
            return self._snapshot.get(exName, {}).get('position', {})
        return {ex: d.get('position', {}) for ex, d in self._snapshot.items()}

    def evtProcess(self, key, *args):
        if len(args) < 3:
            return
        id_, exName = args[0], args[1]
        if id_ == eMarketId['mBalance']:
            self._onBalance(exName, args[2])
        elif id_ == eMarketId['mPosition']:
            self._onPosition(exName, args[2])

    def _onBalance(self, exName: str, balData: dict):
        free = {c: float(v) for c, v in balData.get('free', {}).items() if v and float(v) > 0}
        prev = self._snapshot.setdefault(exName, {}).get('balance', {})
        if free != prev:
            self._snapshot[exName]['balance'] = free
            asyncio.ensure_future(
                evtFireAsync(kEvt_Market, eMarketId['iHolding'], exName, 'balance', free, prev)
            )

    def _onPosition(self, exName: str, positions: list):
        pos = {p['symbol']: p for p in positions if p.get('contracts', 0) != 0}
        prev = self._snapshot.setdefault(exName, {}).get('position', {})
        if pos != prev:
            self._snapshot[exName]['position'] = pos
            asyncio.ensure_future(
                evtFireAsync(kEvt_Market, eMarketId['iHolding'], exName, 'position', pos, prev)
            )

    # async def run(self) -> None:
    #     while True:
    #         await asyncio.sleep(3600)
