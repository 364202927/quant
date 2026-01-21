import type { CandlestickData } from '../types'

/**
 * 生成模拟K线数据
 * @param count 数据条数
 * @param basePrice 基础价格
 */
export function generateMockKlineData(count = 100, basePrice = 45000): CandlestickData[] {
  const data: CandlestickData[] = []
  let price = basePrice
  const now = Math.floor(Date.now() / 1000)

  for (let i = count; i >= 0; i--) {
    const time = now - i * 3600
    const open = price + (Math.random() - 0.5) * 500
    const close = open + (Math.random() - 0.5) * 800
    const high = Math.max(open, close) + Math.random() * 300
    const low = Math.min(open, close) - Math.random() * 300

    data.push({ time, open, high, low, close })
    price = close
  }
  return data
}
