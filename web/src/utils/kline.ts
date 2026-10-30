import type { CandlestickData } from '../types'

export type KlinePeriod = '5m' | '15m' | '30m' | '1h' | '4h' | '1d' | '1w' | '1M'

export const periodOptions: { value: KlinePeriod; label: string }[] = [
  { value: '5m', label: '5m' },
  { value: '15m', label: '15m' },
  { value: '30m', label: '30m' },
  { value: '1h', label: '1h' },
  { value: '4h', label: '4h' },
  { value: '1d', label: 'day' },
  { value: '1w', label: 'week' },
  { value: '1M', label: 'month' },
]

export const fixedPeriodSeconds: Record<KlinePeriod, number> = {
  '5m': 300,
  '15m': 900,
  '30m': 1800,
  '1h': 3600,
  '4h': 14400,
  '1d': 86400,
  '1w': 604800,
  '1M': 0,
}

export function barTimeSeconds(time: CandlestickData['time']): number | null {
  if (typeof time === 'number' && Number.isFinite(time)) return time
  const parsed = Date.parse(String(time))
  return Number.isFinite(parsed) ? parsed / 1000 : null
}

// 周期分桶统一使用 UTC，1w 以周一为起点，1M 以每月 1 日为起点
export function bucketStart(seconds: number, period: KlinePeriod): number {
  if (period === '1M') {
    const date = new Date(seconds * 1000)
    return Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1) / 1000
  }
  if (period === '1w') {
    const date = new Date(seconds * 1000)
    const offset = (date.getUTCDay() + 6) % 7
    return Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate() - offset) / 1000
  }
  const step = fixedPeriodSeconds[period]
  return Math.floor(seconds / step) * step
}

export function nextBucketStart(start: number, period: KlinePeriod): number {
  if (period === '1M') {
    const date = new Date(start * 1000)
    return Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 1) / 1000
  }
  return start + fixedPeriodSeconds[period]
}

// end 用于只聚合前 N 根（模拟回放按已揭示范围重采样）；默认全量
export function resampleKline(
  bars: CandlestickData[],
  period: KlinePeriod,
  end: number = bars.length,
): CandlestickData[] {
  const limit = Math.min(Math.max(end, 0), bars.length)
  if (period === '5m') return limit === bars.length ? bars : bars.slice(0, limit)
  if (limit === 0) return []

  const result: CandlestickData[] = []
  let current: (CandlestickData & { time: number }) | null = null
  for (let i = 0; i < limit; i += 1) {
    const bar = bars[i]
    if (!bar) continue
    const seconds = barTimeSeconds(bar.time)
    if (seconds === null) continue
    const time = bucketStart(seconds, period)
    if (!current || current.time !== time) {
      if (current) result.push(current)
      current = {
        time,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
        volume: bar.volume,
        fundingBps: bar.fundingBps,
      }
      continue
    }
    current.high = Math.max(current.high, bar.high)
    current.low = Math.min(current.low, bar.low)
    current.close = bar.close
    if (bar.volume !== undefined)
      current.volume = (current.volume ?? 0) + bar.volume
    if (bar.fundingBps !== undefined)
      current.fundingBps = bar.fundingBps
  }
  if (current) result.push(current)
  return result
}

// 保留与起止日期有交集的周期 K 线，任一端为空表示该侧不限；周期 > 1d 时取包含该区间的周/月 K 线
export function filterByRange(
  bars: CandlestickData[],
  start: string,
  end: string,
  period: KlinePeriod,
): CandlestickData[] {
  if (!start && !end) return bars
  const rangeStart = start
    ? Date.parse(`${start}T00:00:00Z`) / 1000
    : -Infinity
  const rangeEnd = end
    ? Date.parse(`${end}T00:00:00Z`) / 1000 + 86400
    : Infinity
  if (Number.isNaN(rangeStart) || Number.isNaN(rangeEnd)) return bars

  return bars.filter((bar, index) => {
    const barStart = barTimeSeconds(bar.time)
    if (barStart === null) return false
    const next = bars[index + 1]
    const barEnd = next
      ? barTimeSeconds(next.time)
      : nextBucketStart(barStart, period)
    return barStart < rangeEnd && (barEnd ?? barStart + 1) > rangeStart
  })
}

// 返回时间严格小于 time 的 K 线根数（bars 按时间升序）
export function lowerBoundTime(bars: CandlestickData[], time: number): number {
  let low = 0
  let high = bars.length
  while (low < high) {
    const mid = Math.floor((low + high) / 2)
    const seconds = barTimeSeconds(bars[mid]?.time ?? '')
    if (seconds !== null && seconds < time) low = mid + 1
    else high = mid
  }
  return low
}

const periodBySeconds: { seconds: number; period: KlinePeriod }[] = [
  { seconds: 300, period: '5m' },
  { seconds: 900, period: '15m' },
  { seconds: 1800, period: '30m' },
  { seconds: 3600, period: '1h' },
  { seconds: 14400, period: '4h' },
  { seconds: 86400, period: '1d' },
  { seconds: 604800, period: '1w' },
  { seconds: 2592000, period: '1M' },
]

// 按首个正时间差识别周期；无法识别时回退 5m
export function detectKlinePeriod(bars: CandlestickData[]): KlinePeriod {
  for (let i = 1; i < bars.length; i += 1) {
    const current = barTimeSeconds(bars[i]?.time ?? '')
    const previous = barTimeSeconds(bars[i - 1]?.time ?? '')
    if (current === null || previous === null) continue
    const seconds = Math.round(current - previous)
    if (seconds <= 0) continue
    let nearest = periodBySeconds[0]!
    for (const item of periodBySeconds) {
      if (Math.abs(item.seconds - seconds) < Math.abs(nearest.seconds - seconds)) nearest = item
    }
    return nearest.period
  }
  return '5m'
}
