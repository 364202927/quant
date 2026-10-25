<script setup lang="ts">
import { ref, computed } from 'vue'

interface LogEntry {
  id: number
  time: string
  category: string
  message: string
}

const CATEGORIES = ['全部', '系统', '信号', '订单', '盈亏', '错误']

const emit = defineEmits<{
  close: []
}>()

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
  '系统': 'text-[#b3a590]',
  '信号': 'text-[#93b4d6]',
  '订单': 'text-[#e2bd7a]',
  '盈亏': 'text-[#8fc4a0]',
  '错误': 'text-[#e39a8f]',
}
</script>

<template>
  <aside class="absolute inset-y-0 right-0 z-20 flex w-72 max-w-[85vw] flex-col border-l border-black/30 bg-[#2f2921] text-[#e9dfcc] shadow-2xl xl:static xl:z-auto">
    <!-- 标题栏 -->
    <div class="flex h-14 shrink-0 items-center gap-2 border-b border-white/10 px-3">
      <i class="ri-terminal-box-line text-base text-[#c9a05c]"></i>
      <span class="text-sm font-medium tracking-wide text-[#f4e9d3]">运行日志</span>
      <span class="rounded-full bg-white/10 px-1.5 py-0.5 text-[10px] text-[#b3a590]">{{ filtered.length }}</span>
      <button @click="emit('close')" title="收起日志"
        class="ml-auto flex h-7 w-7 items-center justify-center rounded-md text-[#8f816b] transition-colors hover:bg-white/10 hover:text-[#f4e9d3]">
        <i class="ri-close-line text-base"></i>
      </button>
    </div>

    <!-- 分类筛选 -->
    <div class="shrink-0 border-b border-white/10 px-3 py-2">
      <select v-model="selectedCategory"
        class="w-full rounded-md border border-white/15 bg-[#3a3328] px-2 py-1.5 text-xs text-[#d8ccb5] outline-none transition-colors focus:border-[#c9a05c]">
        <option v-for="cat in CATEGORIES" :key="cat">{{ cat }}</option>
      </select>
    </div>

    <!-- 日志列表 -->
    <div class="min-h-0 flex-1 overflow-y-auto">
      <div v-for="entry in filtered" :key="entry.id"
        class="border-b border-white/5 px-3 py-2 transition-colors hover:bg-white/[0.04]">
        <div class="mb-0.5 flex items-center justify-between gap-2 text-[10px]">
          <span :class="categoryClass[entry.category]" class="font-medium">[{{ entry.category }}]</span>
          <span class="font-mono text-[#7d705d]">{{ entry.time }}</span>
        </div>
        <p class="text-xs leading-relaxed text-[#d8ccb5]">{{ entry.message }}</p>
      </div>
      <p v-if="!filtered.length" class="px-3 py-8 text-center text-xs text-[#7d705d]">暂无日志</p>
    </div>

    <!-- 底部状态 -->
    <div class="flex shrink-0 items-center justify-between border-t border-white/10 px-3 py-2 text-[10px] text-[#8f816b]">
      <span>最近 {{ logData.length }} 条记录</span>
      <span class="font-mono">UTC+8</span>
    </div>
  </aside>
</template>
