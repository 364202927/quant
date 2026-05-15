<script setup lang="ts">
import { ref, computed } from 'vue'

interface LogEntry {
  id: number
  time: string
  category: string
  message: string
}

const CATEGORIES = ['全部', '系统', '信号', '订单', '盈亏', '错误']

const selectedCategory = ref('全部')

const logData = ref<LogEntry[]>([
  { id: 1, time: '2024-01-15 10:30:00', category: '系统', message: '策略启动' },
  { id: 2, time: '2024-01-15 10:30:05', category: '信号', message: '检测到买入信号 BTC/USDT @ 42500' },
  { id: 3, time: '2024-01-15 10:30:06', category: '订单', message: '下单成功: BUY 0.1 BTC @ 42500' },
  { id: 4, time: '2024-01-15 14:20:00', category: '信号', message: '检测到卖出信号 BTC/USDT @ 43200' },
  { id: 5, time: '2024-01-15 14:20:01', category: '订单', message: '下单成功: SELL 0.1 BTC @ 43200' },
  { id: 6, time: '2024-01-15 14:20:02', category: '盈亏', message: '平仓盈利: +70 USDT' },
  { id: 7, time: '2024-01-16 09:15:00', category: '信号', message: '检测到买入信号 BTC/USDT @ 43000' },
  { id: 8, time: '2024-01-16 09:15:01', category: '订单', message: '下单成功: BUY 0.15 BTC @ 43000' },
  { id: 9, time: '2024-01-16 16:45:00', category: '信号', message: '止损触发 BTC/USDT @ 42800' },
  { id: 10, time: '2024-01-16 16:45:01', category: '订单', message: '下单成功: SELL 0.15 BTC @ 42800' },
  { id: 11, time: '2024-01-16 16:45:02', category: '盈亏', message: '平仓亏损: -30 USDT' },
  { id: 12, time: '2024-01-16 16:45:03', category: '错误', message: '网络超时，重试中...' },
  { id: 13, time: '2024-01-16 16:45:10', category: '系统', message: '重连成功' },
])

const filtered = computed(() =>
  selectedCategory.value === '全部'
    ? logData.value
    : logData.value.filter(l => l.category === selectedCategory.value)
)

const categoryClass: Record<string, string> = {
  '系统': 'text-gray-400',
  '信号': 'text-blue-400',
  '订单': 'text-yellow-400',
  '盈亏': 'text-green-400',
  '错误': 'text-red-400',
}
</script>

<template>
  <div class="flex flex-col w-64 bg-gray-900 border-l border-gray-700 shrink-0">
    <!-- 标题栏 -->
    <div class="flex items-center gap-2 px-3 py-2 border-b border-gray-700 shrink-0">
      <span class="text-sm font-medium text-gray-200 whitespace-nowrap">运行日志</span>
      <select v-model="selectedCategory"
        class="flex-1 text-xs bg-gray-800 text-gray-300 border border-gray-600 rounded px-1 py-0.5 min-w-0">
        <option v-for="cat in CATEGORIES" :key="cat">{{ cat }}</option>
      </select>
    </div>

    <!-- 日志列表 -->
    <div class="flex-1 overflow-y-auto min-h-0">
      <div v-for="entry in filtered" :key="entry.id"
        class="px-3 py-1 text-xs font-mono border-b border-gray-800 hover:bg-gray-800">
        <div class="text-gray-500 text-[10px]">{{ entry.time }}</div>
        <div>
          <span :class="categoryClass[entry.category]" class="mr-1">[{{ entry.category }}]</span>
          <span class="text-gray-300">{{ entry.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
