<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import LightweightChart from '../../utils/LightweightChart.vue'
import { generateMockKlineData } from '../../utils/mockData'
import type { CandlestickData } from '../../types'

const klineData = ref<CandlestickData[]>([])
const fearGreedValue = ref(50)
const fearGreedChart = ref<HTMLDivElement | null>(null)
let echartsInstance: echarts.ECharts | null = null

// 获取恐慌贪婪指数颜色
function getFearGreedColor(value: number): string {
  if (value < 25) return '#ef4444'
  if (value < 50) return '#f97316'
  if (value < 75) return '#eab308'
  return '#22c55e'
}

// 初始化恐慌贪婪指数图表
function initFearGreedChart(): void {
  if (!fearGreedChart.value) return

  echartsInstance = echarts.init(fearGreedChart.value)

  const option: echarts.EChartsOption = {
    series: [{
      type: 'gauge',
      startAngle: 180,
      endAngle: 0,
      min: 0,
      max: 100,
      splitNumber: 10,
      itemStyle: {
        color: getFearGreedColor(fearGreedValue.value)
      },
      progress: { show: true, width: 20 },
      pointer: { show: true, length: '60%', width: 6 },
      axisLine: {
        lineStyle: {
          width: 20,
          color: [[0.25, '#ef4444'], [0.5, '#f97316'], [0.75, '#eab308'], [1, '#22c55e']]
        }
      },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: {
        distance: 30,
        color: '#6b7280',
        fontSize: 12,
        formatter: (value: number) => {
          if (value === 0) return '极度恐惧'
          if (value === 50) return '中性'
          if (value === 100) return '极度贪婪'
          return ''
        }
      },
      title: { offsetCenter: [0, '30%'], fontSize: 14, color: '#374151' },
      detail: {
        valueAnimation: true,
        fontSize: 32,
        fontWeight: 'bold',
        offsetCenter: [0, '-10%'],
        formatter: '{value}',
        color: '#1f2937'
      },
      data: [{ value: fearGreedValue.value, name: '恐慌与贪婪指数' }]
    }]
  }

  echartsInstance.setOption(option)
}

function handleResize(): void {
  echartsInstance?.resize()
}

onMounted(() => {
  klineData.value = generateMockKlineData()
  fearGreedValue.value = Math.floor(Math.random() * 100)
  initFearGreedChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  echartsInstance?.dispose()
  echartsInstance = null
})
</script>

<template>
  <div class="h-full flex flex-col gap-4 p-4 overflow-auto">
    <!-- K线图区域 -->
    <div class="bg-white rounded-lg shadow p-4">
      <h3 class="text-lg font-semibold text-gray-800 mb-3">BTC/USDT K线</h3>
      <LightweightChart :data="klineData" :height="350" />
    </div>

    <!-- 恐慌贪婪指数 -->
    <div class="bg-white rounded-lg shadow p-4">
      <h3 class="text-lg font-semibold text-gray-800 mb-3">恐慌与贪婪指数</h3>
      <div ref="fearGreedChart" class="w-full h-64"></div>
    </div>
  </div>
</template>
