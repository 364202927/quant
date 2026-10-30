import { computed, ref, shallowRef, type Ref } from 'vue'
import type { BacktestTradeRecord, CandlestickData } from '../types'
import {
  barTimeSeconds,
  bucketStart,
  lowerBoundTime,
  resampleKline,
  type KlinePeriod,
} from './kline'

type SimSide = 'LONG' | 'SHORT'

interface SimLeg {
  behavior: 'buy' | 'sell'
  time: number
  lv: number
  position: number
}

interface SimRecord {
  dir: SimSide
  legs: SimLeg[]
}

interface SimPosition {
  side: 1 | -1
  dir: SimSide
  entry: number
  qty: number
  margin: number
  lv: number
  recordIndex: number
}

interface SimSnapshot {
  cash: number
  position: SimPosition | null
  records: SimRecord[]
}

function clampPercent(value: number): number {
  return Math.min(Math.max(value, 0), 100)
}

const INITIAL_REVEAL_SECONDS = 30 * 24 * 60 * 60  // 回测从 1 个月开始
const FEE_RATE = 0.0005  // 简单手续费: 0.05%/边
const QTY_EPS = 1e-8

// 模拟回测状态机: 服务端只给 5m K 线, 这里负责按周期揭示、下单、撤销与实时权益
export function useSimBacktest(period: Ref<KlinePeriod>) {
  const symbol = ref('binance_swap_BTCUSDT')
  const principal = ref(1000)
  const bet = ref(10)
  const lv = ref(1)

  const started = ref(false)
  const rawBars = shallowRef<CandlestickData[]>([])
  const revealed = ref(0)
  const cash = ref(0)
  const position = shallowRef<SimPosition | null>(null)
  const records = shallowRef<SimRecord[]>([])
  const snapshot = shallowRef<SimSnapshot | null>(null)

  const fullBars = computed(() => resampleKline(rawBars.value, period.value))
  const displayBars = computed(() =>
    resampleKline(rawBars.value, period.value, revealed.value),
  )
  const hasMore = computed(
    () => started.value && revealed.value < rawBars.value.length,
  )
  const lastBar = computed(() => displayBars.value[displayBars.value.length - 1] ?? null)
  const equity = computed(() => {
    const bar = lastBar.value
    const pos = position.value
    if (!bar || !pos) return cash.value
    return cash.value + (bar.close - pos.entry) * pos.qty * pos.side
  })

  const principalModel = computed<number>({
    get: () => (started.value ? Number(equity.value.toFixed(2)) : principal.value),
    set: (value) => {
      if (!started.value) principal.value = Number(value) || 0
    },
  })

  const tradeRecords = computed<BacktestTradeRecord[]>(() => {
    const indexByTime = new Map<number, number>()
    displayBars.value.forEach((bar, index) => {
      const seconds = barTimeSeconds(bar.time)
      if (seconds !== null) indexByTime.set(seconds, index)
    })
    return records.value.flatMap((record) => {
      const trades = record.legs.flatMap((leg) => {
        const pos =
          indexByTime.get(leg.time) ??
          indexByTime.get(bucketStart(leg.time, period.value))
        if (pos === undefined) return []
        return [{
          behavior: leg.behavior,
          lv: leg.lv,
          pos,
          'position%': leg.position,
        }]
      })
      if (!trades.length) return []
      return [{ type: 'contract', dir: record.dir, trades }]
    })
  })

  function lastRevealedTime(): number {
    const bar = rawBars.value[revealed.value - 1]
    return bar ? (barTimeSeconds(bar.time) ?? 0) : 0
  }

  function cloneSnapshot(): SimSnapshot {
    return {
      cash: cash.value,
      position: position.value ? { ...position.value } : null,
      records: records.value.map((record) => ({
        ...record,
        legs: record.legs.map((leg) => ({ ...leg })),
      })),
    }
  }

  // 揭示从第一根起 initialSeconds 内的 5m K线, 模拟回测固定先看 1 个月
  function revealForDuration(initialSeconds: number): void {
    const first = rawBars.value[0]
    const firstSeconds = first ? barTimeSeconds(first.time) : null
    if (firstSeconds === null) {
      revealed.value = 0
      return
    }
    revealed.value = lowerBoundTime(rawBars.value, firstSeconds + initialSeconds)
  }

  function start(bars: CandlestickData[]): void {
    rawBars.value = bars
    revealed.value = 0
    cash.value = Number(principal.value) || 0
    position.value = null
    records.value = []
    snapshot.value = null
    started.value = true
    revealForDuration(INITIAL_REVEAL_SECONDS)
  }

  function play(): boolean {
    if (!started.value) return false
    const currentIndex = displayBars.value.length - 1
    if (currentIndex < 0) return false
    const boundaryBar = fullBars.value[currentIndex + 2]
    const boundary = boundaryBar
      ? (barTimeSeconds(boundaryBar.time) ?? Infinity)
      : Infinity
    const next = lowerBoundTime(rawBars.value, boundary)
    if (next <= revealed.value) return false
    revealed.value = next
    return true
  }

  function open(dir: SimSide): void {
    if (!started.value || position.value) return
    const bar = lastBar.value
    if (!bar || !(bar.close > 0)) return
    const percent = clampPercent(Number(bet.value) || 0)
    const available = Math.max(equity.value, 0)
    const margin = Math.min((available * percent) / 100, available)
    if (margin <= 0) return
    const leverage = Math.max(Math.floor(Number(lv.value) || 1), 1)
    const notional = margin * leverage
    const pos: SimPosition = {
      side: dir === 'LONG' ? 1 : -1,
      dir,
      entry: bar.close,
      qty: notional / bar.close,
      margin,
      lv: leverage,
      recordIndex: records.value.length,
    }
    snapshot.value = cloneSnapshot()
    cash.value -= notional * FEE_RATE
    position.value = pos
    records.value = [
      ...records.value,
      {
        dir,
        legs: [{
          behavior: dir === 'LONG' ? 'buy' : 'sell',
          time: lastRevealedTime(),
          lv: leverage,
          position: percent,
        }],
      },
    ]
  }

  // 平仓同样按下注百分比: 100% 全平, 其余按比例减仓
  function close(): void {
    if (!started.value) return
    const pos = position.value
    const bar = lastBar.value
    if (!pos || !bar) return
    const percent = clampPercent(Number(bet.value) || 0)
    if (percent <= 0) return
    const fraction = percent / 100
    const closeQty = pos.qty * fraction
    if (closeQty <= QTY_EPS) return
    const full = fraction >= 1 || closeQty >= pos.qty - QTY_EPS
    snapshot.value = cloneSnapshot()
    const realized = (bar.close - pos.entry) * closeQty * pos.side
    cash.value += realized - closeQty * bar.close * FEE_RATE
    const remainingQty = full ? 0 : pos.qty - closeQty
    position.value = full
      ? null
      : {
          ...pos,
          qty: remainingQty,
          margin: pos.margin * (1 - fraction),
        }
    records.value = records.value.map((record, index) => {
      if (index !== pos.recordIndex) return record
      return {
        ...record,
        legs: [
          ...record.legs,
          {
            behavior: pos.side === 1 ? 'sell' : 'buy',
            time: lastRevealedTime(),
            lv: pos.lv,
            position: full ? 100 : fraction * 100,
          },
        ],
      }
    })
  }

  // esc: 仅撤销最近一次下单, 恢复当时的现金/持仓/轨迹
  function undo(): void {
    const saved = snapshot.value
    if (!started.value || !saved) return
    cash.value = saved.cash
    position.value = saved.position
    records.value = saved.records
    snapshot.value = null
  }

  // 开始按钮变为取消测试时调用: 结束并清空本次模拟, 表单值保留
  function cancelTest(): void {
    started.value = false
    rawBars.value = []
    revealed.value = 0
    cash.value = 0
    position.value = null
    records.value = []
    snapshot.value = null
  }

  return {
    symbol,
    principal,
    bet,
    lv,
    started,
    hasMore,
    principalModel,
    displayBars,
    tradeRecords,
    equity,
    start,
    play,
    openLong: () => open('LONG'),
    openShort: () => open('SHORT'),
    close,
    undo,
    cancelTest,
  }
}
