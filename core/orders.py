from collections import deque
from include import *

@singleton
class ordersMsg:
	orderBook = None

	def __init__(self):
		orderBook = deque()

	def addOrder(self):
		pass

	def run():
		if len(orderBook) == 0:
			return

g_ordersMsg = ordersMsg()


# 订单薄回调



# 买单
# 卖单
# 检查单
# 取消单
# 订单状态 

# o = order.Order()
# o.platform  # 交易平台
# o.account  # 交易账户
# o.strategy  # 策略名称
# o.order_no  # 委托单号
# o.action  # 买卖类型 SELL-卖，BUY-买
# o.order_type  # 委托单类型 MKT-市价，LMT-限价
# o.symbol  # 交易对 如: ETH/BTC
# o.price  # 委托价格
# o.quantity  # 委托数量（限价单）
# o.remain  # 剩余未成交数量
# o.status  # 委托单状态
# o.timestamp  # 创建订单时间戳(毫秒)
# o.avg_price  # 成交均价
# o.trade_type  # 合约订单类型 开多/开空/平多/平空
# o.ctime  # 创建订单时间戳
# o.utime  # 交易所订单更新时间