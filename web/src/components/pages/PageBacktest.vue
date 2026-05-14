<script setup lang="ts">
import { ref, inject, onMounted, type Ref } from 'vue'
import LightweightChart from '../../utils/LightweightChart.vue'
import type { CandlestickData, BacktestOrder } from '../../types'

const klineData = ref<CandlestickData[]>([])
const orders = ref<BacktestOrder[]>([])
const activeTab = ref<'orders' | 'results'>('orders')
const isRunning = ref(false)

// inject 必须在 setup 顶层
const taskList = ref<string[]>([])
const selectedTask = ref<string>('')

function formatProfit(profit: number): string {
  if (profit === 0) return '-'
  return profit > 0 ? `+${profit}` : String(profit)
}

function handlePlay() {
  isRunning.value = true
}

function handleRefresh() {
  // TODO: refresh page data
}

onMounted(() => {
  const pageData = inject<Ref<any>>('pageData')
  const list: string[] = pageData?.value
  taskList.value = list
  if (list.length)
    selectedTask.value = list[0]
})
</script>

<template>
  <div class="h-full flex flex-col gap-3 p-4 overflow-hidden">

    <!-- K线图区域 -->
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-4 shrink-0">
      <!-- 实例选择栏 -->
      <div class="flex items-center gap-3 mb-3">
        <span class="text-xs font-semibold text-gray-400 uppercase tracking-widest whitespace-nowrap">实例</span>

        <!-- 实例下拉 -->
        <div class="relative flex-1 max-w-56">
          <select v-model="selectedTask" class="w-full appearance-none bg-gray-50 border border-gray-200 rounded-lg
                   pl-3 pr-8 py-1.5 text-sm font-medium text-gray-700
                   focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent
                   transition-all cursor-pointer">
            <option v-if="!taskList.length" value="" disabled>暂无实例</option>
            <option v-for="task in taskList" :key="task" :value="task">{{ task }}</option>
          </select>
          <svg class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>

        <!-- 操作按钮组 -->
        <div class="ml-auto flex items-center gap-2">
          <!-- 播放按钮 -->
          <button @click="handlePlay" :disabled="isRunning" class="group flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
                   transition-all duration-150 select-none
                   bg-emerald-500 hover:bg-emerald-600 active:scale-95
                   text-white shadow-sm shadow-emerald-200
                   disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100">
            <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>

          </button>

          <!-- 刷新按钮 -->
          <button @click="handleRefresh" class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
                   bg-white/60 border border-gray-200/70 text-gray-500
                   hover:bg-white/90 hover:text-gray-700
                   active:scale-95 transition-all duration-150 backdrop-blur-sm">
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>

          </button>
        </div>
      </div>

      <LightweightChart :data="klineData" :height="240" />
    </div>

    <!-- 下单记录 / 回测结果 -->
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm flex-1 flex flex-col min-h-0">
      <!-- Tab 导航 -->
      <div class="flex items-end gap-1 px-4 pt-3 border-b border-gray-100 shrink-0 bg-white">
        <button v-for="tab in ([
          { key: 'orders', label: '下单记录' },
          { key: 'results', label: '回测结果' },
        ] as const)" :key="tab.key" @click="activeTab = tab.key" class="relative px-4 py-1.5 rounded-t-lg text-sm font-medium transition-all duration-150 select-none
                 border border-b-0 border-transparent bg-transparent" :class="activeTab === tab.key
                  ? 'text-indigo-600 bg-indigo-50/60 border-gray-100'
                  : 'text-gray-400 hover:text-gray-600 hover:bg-gray-50/50'">
          {{ tab.label }}
          <span class="absolute bottom-0 left-0 w-full h-0.5 rounded-t transition-all duration-200"
            :class="activeTab === tab.key ? 'bg-indigo-500' : 'bg-transparent'" />
        </button>
      </div>

      <!-- Tab 内容 -->
      <div class="flex-1 overflow-auto min-h-0">

        <!-- 下单记录 -->
        <template v-if="activeTab === 'orders'">
          <table class="w-full">
            <thead class="bg-gray-50 sticky top-0">
              <tr>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-400 uppercase tracking-wide">时间</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-400 uppercase tracking-wide">交易对</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-400 uppercase tracking-wide">方向</th>
                <th class="px-4 py-2.5 text-right text-xs font-semibold text-gray-400 uppercase tracking-wide">价格</th>
                <th class="px-4 py-2.5 text-right text-xs font-semibold text-gray-400 uppercase tracking-wide">数量</th>
                <th class="px-4 py-2.5 text-right text-xs font-semibold text-gray-400 uppercase tracking-wide">盈亏</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50">
              <tr v-if="!orders.length">
                <td colspan="6" class="px-4 py-12 text-center text-sm text-gray-300">暂无数据</td>
              </tr>
              <tr v-for="order in orders" :key="order.id" class="hover:bg-gray-50 transition-colors duration-75">
                <td class="px-4 py-2.5 text-xs font-mono text-gray-500">{{ order.time }}</td>
                <td class="px-4 py-2.5 text-sm font-medium text-gray-800">{{ order.symbol }}</td>
                <td class="px-4 py-2.5">
                  <span :class="[
                    'inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold',
                    order.side === 'buy'
                      ? 'bg-emerald-50 text-emerald-700'
                      : 'bg-red-50 text-red-700'
                  ]">
                    {{ order.side === 'buy' ? '买入' : '卖出' }}
                  </span>
                </td>
                <td class="px-4 py-2.5 text-sm font-mono text-right text-gray-800">{{ order.price }}</td>
                <td class="px-4 py-2.5 text-sm font-mono text-right text-gray-500">{{ order.amount }}</td>
                <td class="px-4 py-2.5 text-sm font-mono text-right font-semibold"
                  :class="order.profit > 0 ? 'text-emerald-600' : order.profit < 0 ? 'text-red-500' : 'text-gray-300'">
                  {{ formatProfit(order.profit) }}
                </td>
              </tr>
            </tbody>
          </table>
        </template>

        <!-- 回测结果 -->
        <template v-else>
          <div class="p-4 grid grid-cols-2 gap-3">
            <div v-for="metric in [
              { label: '总收益率', value: '--', unit: '%' },
              { label: '夏普比率', value: '--', unit: '' },
              { label: '最大回撤', value: '--', unit: '%' },
              { label: '胜率', value: '--', unit: '%' },
              { label: '总交易次数', value: '--', unit: '次' },
              { label: '年化收益', value: '--', unit: '%' },
            ]" :key="metric.label" class="bg-gray-50 rounded-lg px-4 py-3 flex flex-col gap-1 border border-gray-100">
              <span class="text-xs text-gray-400 font-medium">{{ metric.label }}</span>
              <span class="text-xl font-bold font-mono text-gray-300">
                {{ metric.value }}<span class="text-sm font-normal ml-0.5">{{ metric.unit }}</span>
              </span>
            </div>
          </div>
        </template>

      </div>
    </div>

  </div>
</template>
