<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import LightweightChart from '../../utils/LightweightChart.vue'
import type { CandlestickData } from '../../types'

// 饼图容器
const pieChart = ref<HTMLDivElement | null>(null)
let pieChartInstance: echarts.ECharts | null = null

// K线数据（占位）
const assetKlineData = ref<CandlestickData[]>([])

// 隐私模式
const isPrivate = ref(false)

// 总资产数据（占位）
const totalAssets = ref({
  total: 0,
  todayProfit: 0,
  todayProfitRate: 0,
  currency: 'USDT'
})

// 各交易所资产数据（占位）
const exchangeAssets = ref([
  { name: 'Binance', value: 0, color: '#F0B90B' },
  { name: 'Bybit', value: 0, color: '#F7A600' },
  { name: 'OKEx', value: 0, color: '#1E88E5' }
])

// 初始化饼图
function initPieChart(): void {
  if (!pieChart.value) return

  pieChartInstance = echarts.init(pieChart.value)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} USDT ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { color: '#374151' }
    },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['40%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 8,
        borderColor: '#fff',
        borderWidth: 2
      },
      label: {
        show: false,
        position: 'center'
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 18,
          fontWeight: 'bold'
        }
      },
      labelLine: { show: false },
      data: exchangeAssets.value.map(item => ({
        name: item.name,
        value: item.value,
        itemStyle: { color: item.color }
      }))
    }]
  }

  pieChartInstance.setOption(option)
}

function handleResize(): void {
  pieChartInstance?.resize()
}

// 格式化金额
function formatMoney(value: number): string {
  if (isPrivate.value) return '****'
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// 格式化百分比
function formatPercent(value: number): string {
  if (isPrivate.value) return '**'
  return value.toFixed(2)
}

// 获取收益颜色
function getProfitColor(value: number): string {
  if (value > 0) return 'text-green-500'
  if (value < 0) return 'text-red-500'
  return 'text-gray-500'
}

// 获取收益符号
function getProfitSign(value: number): string {
  return value > 0 ? '+' : ''
}

onMounted(() => {
  initPieChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  pieChartInstance?.dispose()
  pieChartInstance = null
})
</script>

<template>
  <div class="h-full flex flex-col gap-4 p-4 overflow-auto">
    <!-- 顶部资产概览 -->
    <div class="bg-white rounded-lg shadow p-6">
      <div class="flex items-center gap-2 mb-4">
        <h3 class="text-lg font-semibold text-gray-800">资产概览</h3>
        <button @click="isPrivate = !isPrivate" class="text-gray-400 hover:text-gray-600 transition-colors">
          <i :class="isPrivate ? 'ri-eye-off-line' : 'ri-eye-line'" class="text-xl"></i>
        </button>
      </div>
      <div class="flex items-stretch gap-6">
        <!-- 左侧饼图 -->
        <div class="flex-1 min-w-0">
          <div ref="pieChart" class="w-full h-64"></div>
        </div>

        <!-- 右侧总资产信息 -->
        <div class="flex-1 flex flex-col justify-center space-y-4 pl-6 border-l border-gray-200">
          <!-- 总资产 -->
          <div>
            <p class="text-sm text-gray-500 mb-1">总资产估值</p>
            <p class="text-3xl font-bold text-gray-800">
              {{ formatMoney(totalAssets.total) }}
              <span class="text-base font-normal text-gray-500 ml-1">{{ totalAssets.currency }}</span>
            </p>
          </div>

          <!-- 今日收益 -->
          <div>
            <p class="text-sm text-gray-500 mb-1">今日收益</p>
            <div class="flex items-baseline gap-3">
              <p class="text-xl font-semibold" :class="getProfitColor(totalAssets.todayProfit)">
                {{ getProfitSign(totalAssets.todayProfit) }}{{ formatMoney(totalAssets.todayProfit) }}
                <span class="text-sm font-normal ml-1">{{ totalAssets.currency }}</span>
              </p>
              <p class="text-sm" :class="getProfitColor(totalAssets.todayProfitRate)">
                ({{ getProfitSign(totalAssets.todayProfitRate) }}{{ formatPercent(totalAssets.todayProfitRate) }}%)
              </p>
            </div>
          </div>

          <!-- 各交易所资产 -->
          <div class="pt-2">
            <p class="text-sm text-gray-500 mb-2">交易所分布</p>
            <div class="space-y-2">
              <div v-for="item in exchangeAssets" :key="item.name" class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span class="w-3 h-3 rounded-full" :style="{ backgroundColor: item.color }"></span>
                  <span class="text-sm text-gray-700">{{ item.name }}</span>
                </div>
                <span class="text-sm font-medium text-gray-800">{{ formatMoney(item.value) }} USDT</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 资产走势K线图 -->
    <div class="bg-white rounded-lg shadow p-4 flex-1">
      <h3 class="text-lg font-semibold text-gray-800 mb-3">资产走势</h3>
      <LightweightChart :data="assetKlineData" :height="350" />
    </div>
  </div>
</template>
