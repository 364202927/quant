<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { createChart, CandlestickSeries, type IChartApi, type ISeriesApi, type CandlestickData as LWCandlestickData, type Time } from 'lightweight-charts'
import type { CandlestickData } from '../types'

interface Props {
  data: CandlestickData[]
  width?: number
  height?: number
  autosize?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  width: 600,
  height: 400,
  autosize: true
})

const emit = defineEmits<{
  crosshairMove: [param: { time: Time; price: number } | null]
  click: [param: { time: Time; price: number }]
}>()

const chartContainer = ref<HTMLDivElement | null>(null)
let chart: IChartApi | null = null
let candlestickSeries: ISeriesApi<'Candlestick'> | null = null

function initChart(): void {
  if (!chartContainer.value) return

  chart = createChart(chartContainer.value, {
    width: props.autosize ? chartContainer.value.clientWidth : props.width,
    height: props.height,
    layout: {
      background: { color: '#1a1a2e' },
      textColor: '#d1d5db'
    },
    grid: {
      vertLines: { color: '#2d2d44' },
      horzLines: { color: '#2d2d44' }
    },
    crosshair: { mode: 1 },
    rightPriceScale: { borderColor: '#2d2d44' },
    timeScale: {
      borderColor: '#2d2d44',
      timeVisible: true,
      secondsVisible: false
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

  if (props.data.length > 0 && candlestickSeries) {
    candlestickSeries.setData(props.data as LWCandlestickData[])
  }

  chart.subscribeCrosshairMove((param) => {
    if (!param.time || !param.point || !candlestickSeries) {
      emit('crosshairMove', null)
      return
    }
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
  if (chart && chartContainer.value && props.autosize) {
    chart.applyOptions({ width: chartContainer.value.clientWidth })
  }
}

function updateData(newData: CandlestickData[]): void {
  if (candlestickSeries && newData.length > 0) {
    candlestickSeries.setData(newData as LWCandlestickData[])
  }
}

function appendData(bar: CandlestickData): void {
  if (candlestickSeries) {
    candlestickSeries.update(bar as LWCandlestickData)
  }
}

watch(() => props.data, updateData, { deep: true })

onMounted(() => {
  initChart()
  if (props.autosize) {
    window.addEventListener('resize', handleResize)
  }
})

onUnmounted(() => {
  if (props.autosize) {
    window.removeEventListener('resize', handleResize)
  }
  if (chart) {
    chart.remove()
    chart = null
  }
})

defineExpose({ updateData, appendData })
</script>

<template>
  <div ref="chartContainer" class="w-full" :style="{ height: `${height}px` }"></div>
</template>
