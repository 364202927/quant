<script setup lang="ts">
import { ref, onMounted } from 'vue'
import LightweightChart from '../../utils/LightweightChart.vue'
import { generateMockKlineData } from '../../utils/mockData'
import type { CandlestickData, BacktestOrder } from '../../types'

const klineData = ref<CandlestickData[]>([])

const orders = ref<BacktestOrder[]>([
  { id: '1', time: '2024-01-15 10:30', symbol: 'BTC/USDT', side: 'buy', price: 42500, amount: 0.1, profit: 0 },
  { id: '2', time: '2024-01-15 14:20', symbol: 'BTC/USDT', side: 'sell', price: 43200, amount: 0.1, profit: 70 },
  { id: '3', time: '2024-01-16 09:15', symbol: 'BTC/USDT', side: 'buy', price: 43000, amount: 0.15, profit: 0 },
  { id: '4', time: '2024-01-16 16:45', symbol: 'BTC/USDT', side: 'sell', price: 42800, amount: 0.15, profit: -30 }
])

const logs = ref(`[2024-01-15 10:30:00] 策略启动
[2024-01-15 10:30:05] 检测到买入信号 BTC/USDT @ 42500
[2024-01-15 10:30:06] 下单成功: BUY 0.1 BTC @ 42500
[2024-01-15 14:20:00] 检测到卖出信号 BTC/USDT @ 43200
[2024-01-15 14:20:01] 下单成功: SELL 0.1 BTC @ 43200
[2024-01-15 14:20:02] 平仓盈利: +70 USDT
[2024-01-16 09:15:00] 检测到买入信号 BTC/USDT @ 43000
[2024-01-16 09:15:01] 下单成功: BUY 0.15 BTC @ 43000
[2024-01-16 16:45:00] 止损触发 BTC/USDT @ 42800
[2024-01-16 16:45:01] 下单成功: SELL 0.15 BTC @ 42800
[2024-01-16 16:45:02] 平仓亏损: -30 USDT
[2024-01-16 16:45:02] 平仓亏损: -29 USDT
[2024-01-16 16:45:02] 平仓亏损: -28 USDT
[2024-01-16 16:45:02] 平仓亏损: -27 USDT
[2024-01-16 16:45:02] 平仓亏损: -26 USDT
[2024-01-16 16:45:02] 平仓亏损: -25 USDT`)

function formatProfit(profit: number): string {
  if (profit === 0) return '-'
  return profit > 0 ? `+${profit}` : String(profit)
}

onMounted(() => {
  klineData.value = generateMockKlineData(100, 42000)
})
</script>

<template>
  <div class="h-full flex flex-col gap-4 p-4 overflow-hidden">
    <!-- K线图区域 -->
    <div class="bg-white rounded-lg shadow p-4 shrink-0">
      <h3 class="text-lg font-semibold text-gray-800 mb-3">回测K线</h3>
      <LightweightChart :data="klineData" :height="250" />
    </div>

    <!-- 订单表格 -->
    <div class="bg-white rounded-lg shadow flex-1 flex flex-col min-h-0">
      <div class="px-4 py-3 border-b border-gray-200">
        <h3 class="text-lg font-semibold text-gray-800">下单记录</h3>
      </div>
      <div class="flex-1 overflow-auto">
        <table class="w-full">
          <thead class="bg-gray-50 sticky top-0">
            <tr>
              <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">时间</th>
              <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">交易对</th>
              <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">方向</th>
              <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">价格</th>
              <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">数量</th>
              <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">盈亏</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-for="order in orders" :key="order.id" class="hover:bg-gray-50">
              <td class="px-4 py-2 text-sm text-gray-600">{{ order.time }}</td>
              <td class="px-4 py-2 text-sm text-gray-900">{{ order.symbol }}</td>
              <td class="px-4 py-2">
                <span :class="['px-2 py-1 text-xs rounded', order.side === 'buy' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800']">
                  {{ order.side === 'buy' ? '买入' : '卖出' }}
                </span>
              </td>
              <td class="px-4 py-2 text-sm text-gray-900">{{ order.price }}</td>
              <td class="px-4 py-2 text-sm text-gray-600">{{ order.amount }}</td>
              <td class="px-4 py-2 text-sm" :class="order.profit >= 0 ? 'text-green-600' : 'text-red-600'">
                {{ formatProfit(order.profit) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 日志区域 -->
    <div class="bg-white rounded-lg shadow p-4 shrink-0">
      <h3 class="text-lg font-semibold text-gray-800 mb-3">运行日志</h3>
      <textarea
        v-model="logs"
        readonly
        class="w-full h-32 p-3 text-sm font-mono bg-gray-900 text-green-400 rounded-md resize-none"
      ></textarea>
    </div>
  </div>
</template>
