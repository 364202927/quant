<script setup lang="ts">
import { ref } from 'vue'
import type { Strategy, StrategyStatus } from '../../types'

const STRATEGY_STATUS_MAP: Record<StrategyStatus, { class: string; text: string }> = {
  running: { class: 'bg-green-100 text-green-800', text: '运行中' },
  stopped: { class: 'bg-gray-100 text-gray-800', text: '已停止' },
  error: { class: 'bg-red-100 text-red-800', text: '错误' }
}

const strategies = ref<Strategy[]>([
  { id: '1', name: 'BTC网格策略', symbol: 'BTC/USDT', timeframe: '15m', status: 'running', profit: 12.5, winRate: 68 },
  { id: '2', name: 'ETH趋势跟踪', symbol: 'ETH/USDT', timeframe: '1h', status: 'stopped', profit: -3.2, winRate: 45 },
  { id: '3', name: 'SOL突破策略', symbol: 'SOL/USDT', timeframe: '4h', status: 'running', profit: 8.7, winRate: 72 }
])

function addStrategy(): void {
  strategies.value.push({
    id: String(Date.now()),
    name: '新策略',
    symbol: 'BTC/USDT',
    timeframe: '1h',
    status: 'stopped',
    profit: 0,
    winRate: 0
  })
}

function removeStrategy(id: string): void {
  const index = strategies.value.findIndex(s => s.id === id)
  if (index > -1) {
    strategies.value.splice(index, 1)
  }
}

function formatProfit(profit: number): string {
  return profit >= 0 ? `+${profit}%` : `${profit}%`
}
</script>

<template>
  <div class="h-full flex flex-col p-4 overflow-auto">
    <div class="bg-white rounded-lg shadow flex-1 flex flex-col">
      <!-- 表头 -->
      <div class="px-4 py-3 border-b border-gray-200 flex justify-between items-center">
        <h3 class="text-lg font-semibold text-gray-800">策略列表</h3>
        <button
          @click="addStrategy"
          class="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 transition-colors"
        >
          + 添加策略
        </button>
      </div>

      <!-- 表格 -->
      <div class="flex-1 overflow-auto">
        <table class="w-full">
          <thead class="bg-gray-50 sticky top-0">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">名称</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">交易对</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">周期</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">状态</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">收益率</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">胜率</th>
              <th class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-for="strategy in strategies" :key="strategy.id" class="hover:bg-gray-50">
              <td class="px-4 py-3 text-sm font-medium text-gray-900">{{ strategy.name }}</td>
              <td class="px-4 py-3 text-sm text-gray-600">{{ strategy.symbol }}</td>
              <td class="px-4 py-3 text-sm text-gray-600">{{ strategy.timeframe }}</td>
              <td class="px-4 py-3">
                <span :class="['px-2 py-1 text-xs rounded-full', STRATEGY_STATUS_MAP[strategy.status].class]">
                  {{ STRATEGY_STATUS_MAP[strategy.status].text }}
                </span>
              </td>
              <td class="px-4 py-3 text-sm" :class="strategy.profit >= 0 ? 'text-green-600' : 'text-red-600'">
                {{ formatProfit(strategy.profit) }}
              </td>
              <td class="px-4 py-3 text-sm text-gray-600">{{ strategy.winRate }}%</td>
              <td class="px-4 py-3 text-center">
                <button
                  @click="removeStrategy(strategy.id)"
                  class="p-1 text-red-500 hover:text-red-700 hover:bg-red-50 rounded transition-colors"
                  title="删除策略"
                >
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
                  </svg>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
