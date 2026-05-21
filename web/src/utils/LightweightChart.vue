<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'LightweightChart'
})
</script>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import {
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  type HistogramData,
  type IChartApi,
  type ISeriesMarkersPluginApi,
  type ISeriesApi,
  type CandlestickData as LWCandlestickData,
  type LineData,
  type SeriesMarker,
  type Time,
  CrosshairMode // 引入交叉线模式枚举
} from 'lightweight-charts'
import type { BacktestTradeRecord, CandlestickData } from '../types'

interface Props {
  data: CandlestickData[]
  tradeRecords?: BacktestTradeRecord[]
  period?: string
  width?: number
  height?: number
  autosize?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  tradeRecords: () => [],
  period: '',
  width: 600,
  height: 400,
  autosize: true
})

const emit = defineEmits<{
  crosshairMove: [param: { time: Time; price: number } | null]
  click: [param: { time: Time; price: number }]
}>()

const chartContainer = ref<HTMLDivElement | null>(null)
const hoveredBar = ref<CandlestickData | null>(null)
let chart: IChartApi | null = null
let candlestickSeries: ISeriesApi<'Candlestick'> | null = null
let volumeSeries: ISeriesApi<'Histogram'> | null = null
let vwapSeries: ISeriesApi<'Line'> | null = null
let tradeMarkers: ISeriesMarkersPluginApi<Time> | null = null
let dragState: {
  pointerId: number
  startX: number
  startY: number
  startLogicalRange: { from: number; to: number } | null
  startPriceRange: { from: number; to: number } | null
  priceHeight: number
} | null = null

// --- 辅助函数：校验与取值 ---
function isValidNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function volumeValue(bar: CandlestickData): number | null {
  const value = bar.volume
  return isValidNumber(value) ? value : null
}

function vwapValue(bar: CandlestickData): number | null {
  const value = bar.vwap
  return isValidNumber(value) ? value : null
}

function markerText(index: number, dir: string, behavior: string, lv: number, position: number): string {
  const dirKey = dir ? dir.charAt(0).toLowerCase() : ''
  const behaviorKey = behavior ? behavior.charAt(0).toLowerCase() : ''
  return `(${index})${dirKey}${behaviorKey}_lv:${lv}_${position}%`
}

function isTopTradeMarker(dir: string, behavior: string): boolean {
  if (!dir) return behavior === 'buy'
  return (dir === 'SHORT' && behavior === 'sell') || (dir === 'LONG' && behavior === 'buy')
}

function timeToSeconds(time: CandlestickData['time']): number | null {
  if (typeof time === 'number' && Number.isFinite(time)) return time
  const parsed = Date.parse(String(time))
  return Number.isFinite(parsed) ? parsed / 1000 : null
}

function formatPeriod(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${seconds / 60}m`
  if (seconds < 86400) return `${seconds / 3600}h`
  return `${seconds / 86400}d`
}

function formatIndicatorValue(value: number | null | undefined): string {
  if (!isValidNumber(value)) return '--'
  if (Math.abs(value) >= 1000) return value.toFixed(2)
  if (Math.abs(value) >= 1) return value.toFixed(4)
  return value.toFixed(6)
}

function sameBarTime(source: CandlestickData['time'], target: Time): boolean {
  if (typeof source === 'number' && typeof target === 'number') return source === target
  return String(source) === String(target)
}

function resolveBarByTime(time: Time): CandlestickData | null {
  return props.data.find((bar) => sameBarTime(bar.time, time)) ?? null
}

function latestBar(): CandlestickData | null {
  return props.data.length ? props.data[props.data.length - 1] ?? null : null
}

const periodText = computed(() => {
  if (props.period) return props.period
  const times = props.data
    .map((bar) => timeToSeconds(bar.time))
    .filter((time): time is number => time !== null)
  for (let i = 1; i < times.length; i += 1) {
    const current = times[i]
    const previous = times[i - 1]
    if (current === undefined || previous === undefined) continue
    const seconds = Math.round(current - previous)
    if (seconds > 0) return formatPeriod(seconds)
  }
  return '--'
})

const infoBar = computed(() => hoveredBar.value ?? latestBar())

const infoItems = computed(() => {
  const bar = infoBar.value
  if (!bar) return []

  const items = [
    { label: 'O', value: formatIndicatorValue(bar.open) },
    { label: 'H', value: formatIndicatorValue(bar.high) },
    { label: 'L', value: formatIndicatorValue(bar.low) },
    { label: 'C', value: formatIndicatorValue(bar.close) }
  ]

  const volume = volumeValue(bar)
  if (volume !== null) {
    items.push({ label: 'VOL', value: formatIndicatorValue(volume) })
  }

  const vwap = vwapValue(bar)
  if (vwap !== null) {
    items.push({ label: 'VWAP', value: formatIndicatorValue(vwap) })
  }

  return items
})

// --- 指标系列初始化：确保按需创建 ---
function ensureVolumeSeries(): ISeriesApi<'Histogram'> | null {
  if (!chart) return null
  if (!volumeSeries) {
    // 创建量能图系列，配置在独立的 'volume' 坐标轴上
    volumeSeries = chart.addSeries(HistogramSeries, {
      color: 'rgba(148, 163, 184, 0.45)',
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume' // 绑定到自定义坐标轴ID
    })

    // 配置量能图坐标轴的边距，使其显示在底部
    chart.priceScale('volume').applyOptions({
      scaleMargins: {
        top: 0.78, // 距离顶部 78% 的位置开始，留出上方空间给 K 线
        bottom: 0
      }
    })
  }
  return volumeSeries
}

function ensureVwapSeries(): ISeriesApi<'Line'> | null {
  if (!chart) return null
  if (!vwapSeries) {
    vwapSeries = chart.addSeries(LineSeries, {
      color: '#2563eb',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false
    })
  }
  return vwapSeries
}

// --- 数据处理：将原始数据转换为图表所需格式 ---
function updateIndicators(newData: CandlestickData[]): void {
  if (!chart) return

  // 1. 处理成交量数据 (Histogram)
  const volumeData: HistogramData[] = []
  newData.forEach((bar) => {
    const value = volumeValue(bar)
    if (value === null) return
    volumeData.push({
      time: bar.time as Time,
      value,
      // 根据涨跌定义量柱颜色
      color: bar.close >= bar.open ? 'rgba(34, 197, 94, 0.38)' : 'rgba(239, 68, 68, 0.38)'
    })
  })

  if (volumeData.length) {
    ensureVolumeSeries()?.setData(volumeData)
  } else if (volumeSeries) {
    chart.removeSeries(volumeSeries)
    volumeSeries = null
  }

  // 2. 处理 VWAP 数据 (Line)
  const vwapData: LineData[] = []
  newData.forEach((bar) => {
    const value = vwapValue(bar)
    if (value === null) return
    vwapData.push({
      time: bar.time as Time,
      value
    })
  })

  if (vwapData.length) {
    ensureVwapSeries()?.setData(vwapData)
  } else if (vwapSeries) {
    chart.removeSeries(vwapSeries)
    vwapSeries = null
  }
}

function updateTradeMarkers(records: BacktestTradeRecord[]): void {
  if (!candlestickSeries) return

  if (!tradeMarkers) {
    tradeMarkers = createSeriesMarkers(candlestickSeries, [], {
      zOrder: 'top'
    })
  }

  const markers: SeriesMarker<Time>[] = []
  records.forEach((record, recordIndex) => {
    record.trades?.forEach((trade, tradeIndex) => {
      const bar = props.data[trade.pos]
      if (!bar) return

      const isTop = isTopTradeMarker(record.dir, trade.behavior)
      const price = isTop ? bar.high + 80 : bar.low - 80
      markers.push({
        id: `${recordIndex}-${tradeIndex}-${trade.pos}`,
        time: bar.time as Time,
        position: isTop ? 'atPriceTop' : 'atPriceBottom',
        price,
        shape: isTop ? 'arrowDown' : 'arrowUp',
        color: '#f59e0b',
        text: markerText(recordIndex + 1, record.dir, trade.behavior, trade.lv, trade['position%']),
        size: 1.2
      })
    })
  })

  tradeMarkers.setMarkers(markers)
}

function refreshChartData(newData: CandlestickData[]): void {
  if (!candlestickSeries) return
  candlestickSeries.setData(newData as LWCandlestickData[])
  hoveredBar.value = newData.length ? newData[newData.length - 1] ?? null : null
  setPriceVisibleRange(newData)
  updateIndicators(newData)
  updateTradeMarkers(props.tradeRecords)
}

function setPriceVisibleRange(newData: CandlestickData[]): void {
  if (!chart) return
  const prices = newData.flatMap((bar) => [bar.high, bar.low]).filter(isValidNumber)
  if (!prices.length) return

  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const padding = Math.max((max - min) * 0.08, Math.abs(max || min) * 0.001, 1)
  chart.priceScale('right').setVisibleRange({
    from: min - padding,
    to: max + padding
  })
}

function focusTrade(pos: number): void {
  if (!chart || !props.data[pos]) return

  const sideBars = 35
  const from = Math.max(pos - sideBars, 0)
  const to = Math.min(pos + sideBars, props.data.length - 1)
  chart.timeScale().setVisibleLogicalRange({ from, to })

  const visibleBars = props.data.slice(from, to + 1)
  const prices = visibleBars.flatMap((bar) => [bar.high, bar.low]).filter(isValidNumber)
  if (!prices.length) return

  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const padding = Math.max((max - min) * 0.12, Math.abs(max || min) * 0.001, 1)
  chart.priceScale('right').setVisibleRange({
    from: min - padding,
    to: max + padding
  })
}

function handlePointerDown(event: PointerEvent): void {
  if (!chart || !chartContainer.value || !candlestickSeries || event.button !== 0) return
  const rect = chartContainer.value.getBoundingClientRect()
  const localX = event.clientX - rect.left
  const localY = event.clientY - rect.top
  const priceScaleWidth = chart.priceScale('right').width()
  const timeScaleHeight = chart.timeScale().height()

  if (localX >= rect.width - priceScaleWidth || localY >= rect.height - timeScaleHeight) {
    dragState = null
    return
  }

  dragState = {
    pointerId: event.pointerId,
    startX: localX,
    startY: event.clientY,
    startLogicalRange: chart.timeScale().getVisibleLogicalRange(),
    startPriceRange: chart.priceScale('right').getVisibleRange(),
    priceHeight: Math.max(chartContainer.value.clientHeight - chart.timeScale().height(), 1)
  }

  chartContainer.value.setPointerCapture(event.pointerId)
  event.preventDefault()
}

function handlePointerMove(event: PointerEvent): void {
  if (!chart || !chartContainer.value || !dragState || dragState.pointerId !== event.pointerId) return
  const rect = chartContainer.value.getBoundingClientRect()
  const currentX = event.clientX - rect.left

  const logicalRange = dragState.startLogicalRange
  if (logicalRange) {
    const fromX = chart.timeScale().coordinateToLogical(dragState.startX)
    const toX = chart.timeScale().coordinateToLogical(currentX)
    if (fromX !== null && toX !== null) {
      const delta = fromX - toX
      chart.timeScale().setVisibleLogicalRange({
        from: logicalRange.from + delta,
        to: logicalRange.to + delta
      })
    }
  }

  const priceRange = dragState.startPriceRange
  if (priceRange) {
    const size = priceRange.to - priceRange.from
    const delta = (event.clientY - dragState.startY) / dragState.priceHeight * size
    chart.priceScale('right').setVisibleRange({
      from: priceRange.from + delta,
      to: priceRange.to + delta
    })
  }

  event.preventDefault()
}

function handlePointerUp(event: PointerEvent): void {
  if (!chartContainer.value || !dragState || dragState.pointerId !== event.pointerId) return
  chartContainer.value.releasePointerCapture(event.pointerId)
  dragState = null
}

// --- 初始化图表：核心配置修改区 ---
function initChart(): void {
  if (!chartContainer.value) return

  chart = createChart(chartContainer.value, {
    autoSize: props.autosize,
    width: chartContainer.value.clientWidth,
    height: props.height,
    layout: {
      background: { color: '#1a1a2e' },
      textColor: '#d1d5db',
      attributionLogo: false
    },
    grid: {
      vertLines: { color: '#2d2d44' },
      horzLines: { color: '#2d2d44' }
    },
    handleScroll: {
      mouseWheel: true,
      pressedMouseMove: false,
      horzTouchDrag: true,
      vertTouchDrag: true
    },
    handleScale: {
      mouseWheel: true,
      pinch: true,
      axisPressedMouseMove: {
        time: true,
        price: true
      },
      axisDoubleClickReset: {
        time: true,
        price: true
      }
    },
    crosshair: {
      mode: CrosshairMode.Normal
    },
    rightPriceScale: {
      borderColor: '#2d2d44',
      autoScale: false,
    },
    timeScale: {
      borderColor: '#2d2d44',
      timeVisible: true,
      secondsVisible: false,
      rightOffset: 8,
      shiftVisibleRangeOnNewBar: true,
    }
  })

  candlestickSeries = chart.addSeries(CandlestickSeries, {
    upColor: '#22c55e',
    downColor: '#ef4444',
    borderUpColor: '#22c55e',
    borderDownColor: '#ef4444',
    wickUpColor: '#22c55e',
    wickDownColor: '#ef4444'
  })

  chart.priceScale('right').applyOptions({
    autoScale: false,
    scaleMargins: {
      top: 0.1,
      bottom: 0.25
    }
  })

  if (props.data.length > 0 && candlestickSeries) {
    refreshChartData(props.data)
  }

  chart.subscribeCrosshairMove((param) => {
    if (!param.time || !param.point || !candlestickSeries) {
      hoveredBar.value = latestBar()
      emit('crosshairMove', null)
      return
    }
    hoveredBar.value = resolveBarByTime(param.time)
    const price = candlestickSeries.coordinateToPrice(param.point.y) ?? 0
    emit('crosshairMove', { time: param.time, price })
  })

  chart.subscribeClick((param) => {
    if (!param.time || !param.point || !candlestickSeries) return
    const price = candlestickSeries.coordinateToPrice(param.point.y) ?? 0
    emit('click', { time: param.time, price })
  })
}

function handleResize(): void {
  if (!chart || !chartContainer.value) return
  if (!chart.autoSizeActive()) {
    chart.resize(chartContainer.value.clientWidth, props.height, true)
  }
}

function updateData(newData: CandlestickData[]): void {
  refreshChartData(newData)
}

function appendData(bar: CandlestickData): void {
  if (candlestickSeries) {
    candlestickSeries.update(bar as LWCandlestickData)

    const volume = volumeValue(bar)
    if (volume !== null) {
      ensureVolumeSeries()?.update({
        time: bar.time as Time,
        value: volume,
        color: bar.close >= bar.open ? 'rgba(34, 197, 94, 0.38)' : 'rgba(239, 68, 68, 0.38)'
      })
    }

    const vwap = vwapValue(bar)
    if (vwap !== null) {
      ensureVwapSeries()?.update({
        time: bar.time as Time,
        value: vwap
      })
    }
  }
}

watch(() => props.data, (newData) => {
  updateData(newData)
}, { deep: true })

watch(() => props.tradeRecords, (records) => {
  updateTradeMarkers(records)
}, { deep: true })

onMounted(() => {
  initChart()
  chartContainer.value?.addEventListener('pointerdown', handlePointerDown)
  chartContainer.value?.addEventListener('pointermove', handlePointerMove)
  chartContainer.value?.addEventListener('pointerup', handlePointerUp)
  chartContainer.value?.addEventListener('pointercancel', handlePointerUp)
  if (props.autosize) {
    window.addEventListener('resize', handleResize)
  }
})

onUnmounted(() => {
  chartContainer.value?.removeEventListener('pointerdown', handlePointerDown)
  chartContainer.value?.removeEventListener('pointermove', handlePointerMove)
  chartContainer.value?.removeEventListener('pointerup', handlePointerUp)
  chartContainer.value?.removeEventListener('pointercancel', handlePointerUp)
  if (props.autosize) {
    window.removeEventListener('resize', handleResize)
  }
  if (chart) {
    chart.remove()
    chart = null
  }
})

defineExpose({ updateData, appendData, focusTrade })
</script>

<template>
  <div ref="chartContainer" class="relative w-full select-none overflow-hidden"
    :style="{ height: `${height}px`, touchAction: 'none' }">
    <div class="pointer-events-none absolute left-2 top-2 z-10 flex flex-wrap items-center gap-x-3 gap-y-1 rounded bg-black/45 px-2 py-1 text-xs font-semibold text-slate-200">
      <span class="text-slate-100">{{ periodText }}</span>
      <span v-for="item in infoItems" :key="item.label" class="whitespace-nowrap">
        <span class="text-slate-400">{{ item.label }}</span>
        <span class="ml-1 text-slate-100">{{ item.value }}</span>
      </span>
    </div>
  </div>
</template>
