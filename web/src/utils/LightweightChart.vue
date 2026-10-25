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
  /** 撑满父容器高度，用于需要随窗口伸缩的仪表盘图表 */
  fill?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  tradeRecords: () => [],
  period: '',
  width: 600,
  height: 400,
  autosize: true,
  fill: false
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

/** 价格轴下界：K 线不会为负，禁止把标尺拖到 0 以下 */
const priceFloor = 0
let priceClampFrame = 0
let priceClampTimer = 0

// --- 辅助函数：校验与取值 ---
function isValidNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

/** 区间整体上移到 0 之上，保持可视高度不变 */
function clampPriceRange(range: { from: number; to: number }): { from: number; to: number } {
  if (range.from >= priceFloor) return range
  return { from: priceFloor, to: range.to + priceFloor - range.from }
}

function applyPriceRange(range: { from: number; to: number }): void {
  if (!chart) return
  chart.priceScale('right').setVisibleRange(clampPriceRange(range))
}

function clampPriceScale(): void {
  const range = chart?.priceScale('right').getVisibleRange()
  if (range && range.from < priceFloor) applyPriceRange(range)
}

/** 轻量图表自带的轴拖拽/滚轮缩放不经过自定义拖拽，交互后再兜底校正 */
function schedulePriceClamp(): void {
  if (!priceClampFrame) {
    priceClampFrame = requestAnimationFrame(() => {
      priceClampFrame = 0
      clampPriceScale()
    })
  }
  window.clearTimeout(priceClampTimer)
  priceClampTimer = window.setTimeout(clampPriceScale, 60)
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

function timeToSeconds(time: CandlestickData['time'] | Time): number | null {
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

function resolveBarByTime(time: Time): CandlestickData | null {
  const target = timeToSeconds(time)
  if (target === null) return null

  let left = 0
  let right = props.data.length - 1
  while (left <= right) {
    const mid = Math.floor((left + right) / 2)
    const bar = props.data[mid]
    if (!bar) return null
    const barTime = timeToSeconds(bar.time)
    if (barTime === null) return null
    if (barTime === target) return bar
    if (barTime < target) left = mid + 1
    else right = mid - 1
  }
  return null
}

function latestBar(): CandlestickData | null {
  return props.data.length ? props.data[props.data.length - 1] ?? null : null
}

const periodText = computed(() => {
  if (props.period) return props.period
  for (let i = 1; i < props.data.length; i += 1) {
    const currentBar = props.data[i]
    const previousBar = props.data[i - 1]
    if (!currentBar || !previousBar) continue
    const current = timeToSeconds(currentBar.time)
    const previous = timeToSeconds(previousBar.time)
    if (current === null || previous === null) continue
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
  let min = Infinity
  let max = -Infinity
  for (const bar of newData) {
    if (isValidNumber(bar.low)) {
      min = Math.min(min, bar.low)
      max = Math.max(max, bar.low)
    }
    if (isValidNumber(bar.high)) {
      min = Math.min(min, bar.high)
      max = Math.max(max, bar.high)
    }
  }
  if (min === Infinity) return

  const padding = Math.max((max - min) * 0.08, Math.abs(max || min) * 0.001, 1)
  applyPriceRange({
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
  applyPriceRange({
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
  if (!chart || !chartContainer.value) return
  if (!dragState || dragState.pointerId !== event.pointerId) return
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
    applyPriceRange({
      from: priceRange.from + delta,
      to: priceRange.to + delta
    })
  }

  event.preventDefault()
}

function handlePointerUp(event: PointerEvent): void {
  if (!chartContainer.value) return
  schedulePriceClamp()
  if (!dragState || dragState.pointerId !== event.pointerId) return
  chartContainer.value.releasePointerCapture(event.pointerId)
  dragState = null
}

// --- 初始化图表：核心配置修改区 ---
function initChart(): void {
  if (!chartContainer.value) return

  chart = createChart(chartContainer.value, {
    autoSize: props.autosize,
    width: chartContainer.value.clientWidth,
    height: props.fill ? chartContainer.value.clientHeight : props.height,
    layout: {
      background: { color: '#fbf7ec' },
      textColor: '#74664f',
      attributionLogo: false
    },
    grid: {
      vertLines: { color: '#eadfc8' },
      horzLines: { color: '#eadfc8' }
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
      borderColor: '#ddd0b2',
      autoScale: false,
    },
    timeScale: {
      borderColor: '#ddd0b2',
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
    const height = props.fill ? chartContainer.value.clientHeight : props.height
    chart.resize(chartContainer.value.clientWidth, height, true)
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
})

watch(() => props.tradeRecords, (records) => {
  updateTradeMarkers(records)
})

onMounted(() => {
  initChart()
  chartContainer.value?.addEventListener('pointerdown', handlePointerDown)
  chartContainer.value?.addEventListener('pointermove', handlePointerMove)
  chartContainer.value?.addEventListener('pointerup', handlePointerUp)
  chartContainer.value?.addEventListener('pointercancel', handlePointerUp)
  chartContainer.value?.addEventListener('wheel', schedulePriceClamp, { passive: true })
  // 释放在时间轴等内部元素时事件不会冒泡到容器，用 window 捕获阶段兜底
  window.addEventListener('pointerup', schedulePriceClamp, true)
  window.addEventListener('pointercancel', schedulePriceClamp, true)
  if (props.autosize) {
    window.addEventListener('resize', handleResize)
  }
})

onUnmounted(() => {
  chartContainer.value?.removeEventListener('pointerdown', handlePointerDown)
  chartContainer.value?.removeEventListener('pointermove', handlePointerMove)
  chartContainer.value?.removeEventListener('pointerup', handlePointerUp)
  chartContainer.value?.removeEventListener('pointercancel', handlePointerUp)
  chartContainer.value?.removeEventListener('wheel', schedulePriceClamp)
  window.removeEventListener('pointerup', schedulePriceClamp, true)
  window.removeEventListener('pointercancel', schedulePriceClamp, true)
  if (priceClampFrame) {
    cancelAnimationFrame(priceClampFrame)
    priceClampFrame = 0
  }
  window.clearTimeout(priceClampTimer)
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
    :style="fill ? { height: '100%', minHeight: '240px', touchAction: 'none' } : { height: `${height}px`, touchAction: 'none' }">
    <div v-if="data.length" class="pointer-events-none absolute left-2 top-2 z-10 flex flex-wrap items-center gap-x-3 gap-y-1 rounded border border-paper-line/80 bg-paper/90 px-2 py-1 text-xs font-semibold text-ink-soft backdrop-blur-sm">
      <span class="text-ink">{{ periodText }}</span>
      <span v-for="item in infoItems" :key="item.label" class="whitespace-nowrap">
        <span class="text-ink-faint">{{ item.label }}</span>
        <span class="ml-1 text-ink">{{ item.value }}</span>
      </span>
    </div>
    <div v-else class="absolute inset-0 z-10 flex items-center justify-center bg-paper-soft">
      <div class="flex flex-col items-center gap-2 text-ink-faint">
        <i class="ri-line-chart-line text-2xl"></i>
        <span class="text-xs">暂无 K 线数据</span>
      </div>
    </div>
  </div>
</template>
