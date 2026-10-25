<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Order, OrderStatus } from '../../types'

const ORDER_STATUS_MAP: Record<OrderStatus, { class: string; text: string }> = {
  open: { class: 'bg-blue-100 text-blue-800', text: '进行中' },
  closed: { class: 'bg-green-100 text-green-800', text: '已完成' },
  canceled: { class: 'bg-gray-100 text-gray-800', text: '已取消' }
}

const FILTER_OPTIONS = [
  { value: 'all', label: '全部订单' },
  { value: 'open', label: '进行中' },
  { value: 'closed', label: '已完成' },
  { value: 'canceled', label: '已取消' }
] as const

const selectedFilter = ref<'all' | OrderStatus>('all')

const orders = ref<Order[]>([
  { id: '1', symbol: 'BTC/USDT', side: 'buy', type: 'limit', price: 42500, amount: 0.1, filled: 0.1, status: 'closed', timestamp: Date.now() - 3600000 },
  { id: '2', symbol: 'ETH/USDT', side: 'sell', type: 'market', price: 2250, amount: 1.5, filled: 1.5, status: 'closed', timestamp: Date.now() - 7200000 },
  { id: '3', symbol: 'SOL/USDT', side: 'buy', type: 'limit', price: 98.5, amount: 10, filled: 5, status: 'open', timestamp: Date.now() - 1800000 },
  { id: '4', symbol: 'BTC/USDT', side: 'sell', type: 'limit', price: 45000, amount: 0.05, filled: 0, status: 'canceled', timestamp: Date.now() - 86400000 }
])

const filteredOrders = computed(() => {
  if (selectedFilter.value === 'all') return orders.value
  return orders.value.filter(o => o.status === selectedFilter.value)
})

function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleString('zh-CN')
}
</script>

<template>
  <div class="page-body flex flex-col">
    <section class="panel flex flex-1 flex-col overflow-hidden">
      <!-- 筛选区域 -->
      <div class="panel-header flex-wrap">
        <div class="flex items-center gap-3">
          <h2 class="panel-title">订单流水</h2>
          <span class="text-xs text-ink-faint">共 {{ filteredOrders.length }} 条记录</span>
        </div>
        <label class="flex items-center gap-2 text-xs text-ink-soft">
          订单状态
          <select
            v-model="selectedFilter"
            class="rounded-lg border border-paper-line bg-paper px-2.5 py-1.5 text-xs text-ink outline-none transition-colors focus:border-indigo-400"
          >
            <option v-for="opt in FILTER_OPTIONS" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </label>
      </div>

      <!-- 表格 -->
      <div class="flex-1 overflow-auto">
        <table class="w-full min-w-[760px]">
          <thead class="sticky top-0 bg-paper-deep/70 backdrop-blur">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-ink-soft">时间</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-ink-soft">交易对</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-ink-soft">方向</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-ink-soft">类型</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-ink-soft">价格</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-ink-soft">数量</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-ink-soft">已成交</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-ink-soft">状态</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-paper-line/70">
            <tr v-if="!filteredOrders.length">
              <td colspan="8" class="px-4 py-12 text-center text-sm text-ink-faint">当前筛选条件下暂无订单</td>
            </tr>
            <tr v-for="order in filteredOrders" :key="order.id" class="transition-colors hover:bg-paper-deep/40">
              <td class="px-4 py-3 font-mono text-xs text-ink-soft">{{ formatTime(order.timestamp) }}</td>
              <td class="px-4 py-3 text-sm font-medium text-ink">{{ order.symbol }}</td>
              <td class="px-4 py-3">
                <span :class="['px-2 py-1 text-xs rounded', order.side === 'buy' ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800']">
                  {{ order.side === 'buy' ? '买入' : '卖出' }}
                </span>
              </td>
              <td class="px-4 py-3 text-sm text-ink-soft">{{ order.type === 'market' ? '市价' : '限价' }}</td>
              <td class="px-4 py-3 font-mono text-sm text-ink">{{ order.price }}</td>
              <td class="px-4 py-3 font-mono text-sm text-ink-soft">{{ order.amount }}</td>
              <td class="px-4 py-3 font-mono text-sm text-ink-soft">{{ order.filled }}</td>
              <td class="px-4 py-3">
                <span :class="['px-2 py-1 text-xs rounded-full', ORDER_STATUS_MAP[order.status].class]">
                  {{ ORDER_STATUS_MAP[order.status].text }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
