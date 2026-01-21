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
  <div class="h-full flex flex-col p-4 overflow-hidden">
    <div class="bg-white rounded-lg shadow flex-1 flex flex-col">
      <!-- 筛选区域 -->
      <div class="px-4 py-3 border-b border-gray-200 flex items-center gap-4">
        <label class="text-sm font-medium text-gray-700">订单状态:</label>
        <select
          v-model="selectedFilter"
          class="px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
        >
          <option v-for="opt in FILTER_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
        <span class="text-sm text-gray-500">共 {{ filteredOrders.length }} 条记录</span>
      </div>

      <!-- 表格 -->
      <div class="flex-1 overflow-auto">
        <table class="w-full">
          <thead class="bg-gray-50 sticky top-0">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">时间</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">交易对</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">方向</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">类型</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">价格</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">数量</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">已成交</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">状态</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-for="order in filteredOrders" :key="order.id" class="hover:bg-gray-50">
              <td class="px-4 py-3 text-sm text-gray-600">{{ formatTime(order.timestamp) }}</td>
              <td class="px-4 py-3 text-sm font-medium text-gray-900">{{ order.symbol }}</td>
              <td class="px-4 py-3">
                <span :class="['px-2 py-1 text-xs rounded', order.side === 'buy' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800']">
                  {{ order.side === 'buy' ? '买入' : '卖出' }}
                </span>
              </td>
              <td class="px-4 py-3 text-sm text-gray-600">{{ order.type === 'market' ? '市价' : '限价' }}</td>
              <td class="px-4 py-3 text-sm text-gray-900">{{ order.price }}</td>
              <td class="px-4 py-3 text-sm text-gray-600">{{ order.amount }}</td>
              <td class="px-4 py-3 text-sm text-gray-600">{{ order.filled }}</td>
              <td class="px-4 py-3">
                <span :class="['px-2 py-1 text-xs rounded-full', ORDER_STATUS_MAP[order.status].class]">
                  {{ ORDER_STATUS_MAP[order.status].text }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
