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
  <div class="page-body flex flex-col">
    <section class="panel flex flex-1 flex-col overflow-hidden">
      <!-- 表头 -->
      <div class="panel-header">
        <div class="flex items-baseline gap-2">
          <h2 class="panel-title">策略列表</h2>
          <span class="text-xs text-ink-faint">{{ strategies.length }} 个实例</span>
        </div>
        <button
          @click="addStrategy"
          class="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700"
        >
          <i class="ri-add-line"></i>
          添加策略
        </button>
      </div>

      <!-- 表格 -->
      <div class="flex-1 overflow-auto">
        <table class="w-full min-w-[640px]">
          <thead class="sticky top-0 bg-paper-deep/70 backdrop-blur">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-ink-soft">名称</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-ink-soft">交易对</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-ink-soft">周期</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-ink-soft">状态</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-ink-soft">收益率</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-ink-soft">胜率</th>
              <th class="px-4 py-3 text-center text-xs font-medium text-ink-soft">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-paper-line/70">
            <tr v-if="!strategies.length">
              <td colspan="7" class="px-4 py-12 text-center text-sm text-ink-faint">暂无策略，点击右上角添加</td>
            </tr>
            <tr v-for="strategy in strategies" :key="strategy.id" class="transition-colors hover:bg-paper-deep/40">
              <td class="px-4 py-3 text-sm font-medium text-ink">{{ strategy.name }}</td>
              <td class="px-4 py-3 text-sm text-ink-soft">{{ strategy.symbol }}</td>
              <td class="px-4 py-3 text-sm text-ink-soft">{{ strategy.timeframe }}</td>
              <td class="px-4 py-3">
                <span :class="['px-2 py-1 text-xs rounded-full', STRATEGY_STATUS_MAP[strategy.status].class]">
                  {{ STRATEGY_STATUS_MAP[strategy.status].text }}
                </span>
              </td>
              <td class="px-4 py-3 text-sm font-medium" :class="strategy.profit >= 0 ? 'text-emerald-700' : 'text-rose-700'">
                {{ formatProfit(strategy.profit) }}
              </td>
              <td class="px-4 py-3 text-sm text-ink-soft">{{ strategy.winRate }}%</td>
              <td class="px-4 py-3 text-center">
                <button
                  @click="removeStrategy(strategy.id)"
                  class="rounded-md p-1.5 text-rose-600 transition-colors hover:bg-rose-50 hover:text-rose-700"
                  title="删除策略"
                >
                  <i class="ri-delete-bin-line text-base"></i>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
