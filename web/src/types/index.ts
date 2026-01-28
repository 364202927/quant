// 通用类型
export type TradeSide = 'buy' | 'sell'
export type OrderType = 'market' | 'limit'
export type OrderStatus = 'open' | 'closed' | 'canceled'
export type StrategyStatus = 'running' | 'stopped' | 'error'

// K线数据
export interface CandlestickData {
  time: number | string
  open: number
  high: number
  low: number
  close: number
  volume?: number
}

// 策略
export interface Strategy {
  id: string
  name: string
  symbol: string
  timeframe: string
  status: StrategyStatus
  profit: number
  winRate: number
}

// 订单
export interface Order {
  id: string
  symbol: string
  side: TradeSide
  type: OrderType
  price: number
  amount: number
  filled: number
  status: OrderStatus
  timestamp: number
}

// 回测订单
export interface BacktestOrder {
  id: string
  time: string
  symbol: string
  side: TradeSide
  price: number
  amount: number
  profit: number
}

// 菜单项
export interface MenuItem {
  id: number
  name: string
  icon: string
}

export enum eMsg {
  // get 数据
  eWebInit = 1000,     // web 初始化
  ePage_k = 1001,      // 行情
  ePage_cta = 1002,
  ePage_test = 1003,
  ePage_order = 1004,

  // save 数据
  eSaveFile = 10000,   // 同步后台
}