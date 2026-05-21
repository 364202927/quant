<script setup lang="ts">
import { computed, ref, inject, nextTick, onMounted, type Ref } from 'vue'
import LightweightChart from '../../utils/LightweightChart.vue'
import { eMsg, type BacktestTrade, type BacktestTradeRecord, type CandlestickData } from '../../types'
import { postMessage } from '../../utils/common'

const klineData = ref<CandlestickData[]>([])
const tradeRecords = ref<BacktestTradeRecord[]>([])
const backtestSummary = ref<Record<string, unknown> | null>(null)
const expandedRecords = ref<Set<number>>(new Set())
const chartRef = ref<InstanceType<typeof LightweightChart> | null>(null)
const activeTab = ref<'orders' | 'results'>('orders')
const isRunning = ref(false)

const tabs = [
  { key: 'orders', label: '交易轨迹' },
  { key: 'results', label: '回测结果' },
] as const

type SummaryTone = 'profit' | 'risk' | 'score' | 'verdict' | 'neutral'

type SummaryMetricConfig = {
  label: string
  path: string
  unit?: string
  digits?: number
  tone?: SummaryTone
  important?: boolean
}

type SummaryMetric = SummaryMetricConfig & {
  value: string
  raw: unknown
}

const highlightMetricConfigs: SummaryMetricConfig[] = [
  { label: '综合评分', path: 'score.total_score', tone: 'score', important: true },
  { label: '最终建议', path: 'score.verdict', tone: 'verdict', important: true },
  { label: '总收益率', path: 'return_quality.total_return_pct', unit: '%', tone: 'profit', important: true },
  { label: '净利润', path: 'basic.net_profit', tone: 'profit', important: true },
  { label: '最大回撤', path: 'live_tolerance.max_drawdown_pct', unit: '%', tone: 'risk', important: true },
  { label: '夏普', path: 'overfit_filter.sharpe_ratio', digits: 4, tone: 'profit', important: true },
  { label: '胜率', path: 'basic.win_rate_pct', unit: '%', tone: 'profit', important: true },
  { label: '盈亏比', path: 'return_quality.profit_factor', digits: 4, tone: 'profit', important: true },
]

const summaryGroupConfigs: { title: string; metrics: SummaryMetricConfig[] }[] = [
  {
    title: '基础',
    metrics: [
      { label: '初始本金', path: 'basic.initial_principal' },
      { label: '剩余资金', path: 'basic.remaining_capital', tone: 'profit' },
      { label: '当前保证金', path: 'basic.margin' },
      { label: '杠杆', path: 'basic.leverage', unit: 'x' },
      { label: '总交易', path: 'basic.n_trades', unit: '次' },
      { label: '交易日', path: 'basic.trading_days', unit: '天' },
      { label: '手续费', path: 'basic.total_trade_fee' },
      { label: '资金费', path: 'basic.total_funding_fee' },
    ]
  },
  {
    title: '收益',
    metrics: [
      { label: '年化收益', path: 'return_quality.cagr_pct', unit: '%', tone: 'profit' },
      { label: '总收益', path: 'return_quality.total_return_pct', unit: '%', tone: 'profit' },
      { label: '总盈利', path: 'return_quality.total_win_amount', tone: 'profit' },
      { label: '总亏损', path: 'return_quality.total_loss_amount', tone: 'risk' },
      { label: '盈利单', path: 'return_quality.win_count', unit: '次' },
      { label: '亏损单', path: 'return_quality.loss_count', unit: '次' },
      { label: '最大盈利', path: 'return_quality.max_single_win', tone: 'profit' },
      { label: '最大亏损', path: 'return_quality.max_single_loss', tone: 'risk' },
      { label: '周胜率', path: 'return_quality.weekly_win_rate_pct', unit: '%', tone: 'profit' },
      { label: '月胜率', path: 'return_quality.monthly_win_rate_pct', unit: '%', tone: 'profit' },
      { label: '平均盈亏比', path: 'return_quality.win_loss_ratio', digits: 4, tone: 'profit' },
      { label: '收益偏度', path: 'return_quality.return_skewness', digits: 4, tone: 'profit' },
    ]
  },
  {
    title: '风险',
    metrics: [
      { label: '最大回撤', path: 'live_tolerance.max_drawdown_pct', unit: '%', tone: 'risk' },
      { label: '回撤持续', path: 'live_tolerance.drawdown_duration_trades', unit: '笔' },
      { label: '最大连亏', path: 'live_tolerance.max_consecutive_losses', unit: '次', tone: 'risk' },
      { label: '最大连赢', path: 'live_tolerance.max_consecutive_wins', unit: '次', tone: 'profit' },
      { label: '恢复天数', path: 'live_tolerance.recovery_days', unit: '天' },
      { label: '日波动', path: 'post_cost_survival.daily_volatility', digits: 6, tone: 'risk' },
      { label: '年化波动', path: 'post_cost_survival.annual_volatility', digits: 4, tone: 'risk' },
      { label: 'CVaR95', path: 'post_cost_survival.cvar_95_pct', unit: '%', tone: 'risk' },
      { label: 'CVaR99', path: 'post_cost_survival.cvar_99_pct', unit: '%', tone: 'risk' },
      { label: '波动偏差', path: 'post_cost_survival.volatility_deviation_pct', unit: '%', tone: 'risk' },
    ]
  },
  {
    title: '稳健',
    metrics: [
      { label: '夏普', path: 'overfit_filter.sharpe_ratio', digits: 4, tone: 'profit' },
      { label: '索提诺', path: 'overfit_filter.sortino_ratio', digits: 4, tone: 'profit' },
      { label: '卡玛', path: 'overfit_filter.calmar_ratio', digits: 4, tone: 'profit' },
      { label: '紧缩夏普', path: 'overfit_filter.deflated_sharpe', digits: 4, tone: 'profit' },
      { label: '紧缩P值', path: 'overfit_filter.deflated_sharpe_pvalue', digits: 4, tone: 'risk' },
      { label: 'OOS衰减', path: 'live_tolerance.oos_sharpe_decay', digits: 4, tone: 'profit' },
      { label: '滚动夏普低点', path: 'live_tolerance.rolling_sharpe_min', digits: 4, tone: 'profit' },
      { label: '滚动夏普波动', path: 'live_tolerance.rolling_sharpe_std', digits: 4, tone: 'risk' },
      { label: '原始利润', path: 'live_tolerance.stress_original_profit', tone: 'profit' },
      { label: '2x滑点利润', path: 'live_tolerance.stress_2x_slip_profit', tone: 'profit' },
      { label: '年化换手', path: 'live_tolerance.turnover_rate_annual', digits: 4, tone: 'risk' },
      { label: '容量估算', path: 'live_tolerance.capacity_estimate', unit: '万', tone: 'profit' },
    ]
  }
]

// inject 必须在 setup 顶层
const taskList = ref<string[]>([])
const selectedTask = ref<string>('')

type KlineRow = Partial<CandlestickData> & {
  vol?: number | null
  [key: string]: unknown
}

interface BacktestPayload {
  kLine?: KlineRow[]
  pf?: KlineRow[]
  tradeRecords?: BacktestTradeRecord[]
  summarize?: Record<string, unknown>
}

type TradeTableRow = {
  key: string
  kind: 'parent' | 'child'
  record: BacktestTradeRecord
  recordIndex: number
  trade?: BacktestTrade
  nextTrade?: BacktestTrade
  tradeIndex?: number
}

function toNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  const num = Number(value)
  return Number.isFinite(num) ? num : null
}

function getSummaryValue(source: Record<string, unknown> | null, path: string): unknown {
  if (!source) return null
  return path.split('.').reduce<unknown>((current, key) => {
    if (current === null || current === undefined || typeof current !== 'object') return null
    return (current as Record<string, unknown>)[key]
  }, source)
}

function formatSummaryValue(raw: unknown, digits = 2): string {
  if (raw === null || raw === undefined || raw === '') return '--'
  if (typeof raw === 'string') return raw
  if (typeof raw === 'boolean') return raw ? '是' : '否'
  const num = Number(raw)
  if (!Number.isFinite(num)) return String(raw)
  if (Number.isInteger(num)) return String(num)
  return num.toFixed(digits)
}

function summaryValueClass(config: SummaryMetricConfig, raw: unknown): string {
  const tone = config.tone ?? 'neutral'
  const important = config.important

  if (typeof raw === 'string') {
    if (tone === 'verdict') {
      if (raw.includes('可实盘')) return 'text-emerald-600'
      if (raw.includes('继续改善')) return 'text-amber-600'
      return 'text-rose-600'
    }
    return important ? 'text-slate-900' : 'text-slate-700'
  }

  const num = Number(raw)
  if (!Number.isFinite(num)) return important ? 'text-slate-900' : 'text-slate-600'

  if (config.path === 'score.total_score') {
    if (num >= 80) return 'text-emerald-600'
    if (num >= 60) return 'text-amber-600'
    return 'text-rose-600'
  }

  if (config.path === 'overfit_filter.deflated_sharpe_pvalue') {
    if (num <= 0.05) return 'text-emerald-600'
    if (num <= 0.1) return 'text-amber-600'
    return 'text-rose-600'
  }

  if (config.path === 'live_tolerance.oos_sharpe_decay') {
    if (num >= -0.3) return 'text-emerald-600'
    if (num >= -0.5) return 'text-amber-600'
    return 'text-rose-600'
  }

  if (config.path === 'live_tolerance.max_drawdown_pct'
    || config.path === 'live_tolerance.drawdown_duration_trades'
    || config.path === 'live_tolerance.max_consecutive_losses'
    || config.path === 'post_cost_survival.daily_volatility'
    || config.path === 'post_cost_survival.annual_volatility'
    || config.path === 'post_cost_survival.cvar_95_pct'
    || config.path === 'post_cost_survival.cvar_99_pct'
    || config.path === 'post_cost_survival.volatility_deviation_pct'
    || config.path === 'live_tolerance.rolling_sharpe_std'
    || config.path === 'live_tolerance.turnover_rate_annual'
    || config.path === 'return_quality.total_loss_amount'
    || config.path === 'return_quality.max_single_loss'
    || config.path === 'basic.total_trade_fee'
    || config.path === 'basic.total_funding_fee') {
    return num <= 0 ? 'text-emerald-600' : 'text-rose-600'
  }

  if (tone === 'profit') return num >= 0 ? 'text-emerald-600' : 'text-rose-600'
  if (tone === 'risk') return num <= 0 ? 'text-emerald-600' : 'text-rose-600'
  return important ? 'text-slate-900' : 'text-slate-700'
}

function summaryCardClass(config: SummaryMetricConfig, raw: unknown): string {
  const important = config.important
  const tone = summaryValueClass(config, raw)
  return [
    'rounded-lg border px-4 py-3 flex flex-col gap-1',
    important ? 'bg-slate-50 border-slate-200' : 'bg-gray-50 border-gray-100',
    tone.includes('emerald') ? 'shadow-[inset_0_0_0_1px_rgba(16,185,129,0.18)]' : '',
    tone.includes('rose') ? 'shadow-[inset_0_0_0_1px_rgba(244,63,94,0.12)]' : ''
  ].filter(Boolean).join(' ')
}

function buildSummaryMetric(config: SummaryMetricConfig): SummaryMetric | null {
  const raw = getSummaryValue(backtestSummary.value, config.path)
  if (raw === null || raw === undefined) return null
  return {
    ...config,
    raw,
    value: formatSummaryValue(raw, config.digits ?? 2)
  }
}

const summaryHighlights = computed<SummaryMetric[]>(() => highlightMetricConfigs
  .map((config) => buildSummaryMetric(config))
  .filter((item): item is SummaryMetric => item !== null))

const summarySections = computed(() => summaryGroupConfigs
  .map((group) => ({
    title: group.title,
    metrics: group.metrics
      .map((config) => buildSummaryMetric(config))
      .filter((item): item is SummaryMetric => item !== null)
  }))
  .filter((group) => group.metrics.length > 0))

const scoreDetails = computed(() => {
  const details = getSummaryValue(backtestSummary.value, 'score.details')
  return Array.isArray(details) ? details.map((item) => String(item)) : []
})

function normalizeKline(rows: unknown): CandlestickData[] {
  if (!Array.isArray(rows)) return []

  const result: CandlestickData[] = []

  rows.forEach((row) => {
    const item = row as KlineRow
    const open = toNumber(item.open)
    const high = toNumber(item.high)
    const low = toNumber(item.low)
    const close = toNumber(item.close)

    if (item.time === undefined || open === null || high === null || low === null || close === null)
      return

    const bar: CandlestickData = {
      time: typeof item.time === 'number' ? item.time : String(item.time),
      open, high, low, close
    }

    const volume = toNumber(item.volume ?? item.vol)
    if (volume !== null)
      bar.volume = volume

    const vwap = toNumber(item.vwap)
    if (vwap !== null)
      bar.vwap = vwap

    result.push(bar)
  })

  return result
}

function normalizeTradeRecords(records: unknown): BacktestTradeRecord[] {
  if (!Array.isArray(records)) return []

  return records.flatMap((record) => {
    const item = record as BacktestTradeRecord
    if (!Array.isArray(item.trades)) return []
    return [{
      type: String(item.type ?? ''),
      dir: String(item.dir ?? ''),
      trades: item.trades.flatMap((trade) => {
        const pos = toNumber(trade.pos)
        const lv = toNumber(trade.lv)
        const position = toNumber(trade['position%'])
        if (trade.behavior !== 'buy' && trade.behavior !== 'sell') return []
        if (pos === null || lv === null || position === null) return []
        return [{
          behavior: trade.behavior,
          lv,
          pos,
          'position%': position
        }]
      })
    }]
  })
}

function formatTimeByPos(pos: number): string {
  const time = klineData.value[pos]?.time
  if (time === undefined) return '-'
  if (typeof time === 'number') {
    return new Date(time * 1000).toLocaleString()
  }
  return String(time)
}

function firstTrade(record: BacktestTradeRecord): BacktestTrade | undefined {
  return record.trades[0]
}

function directionText(record: BacktestTradeRecord, trade?: BacktestTrade): string {
  if (!trade) return '-'
  return `${record.dir || ''}_${trade.behavior}`
}

function durationMinutes(record: BacktestTradeRecord): number | string {
  const first = record.trades[0]
  const last = record.trades[record.trades.length - 1]
  if (!first || !last) return '-'
  return durationBetweenTrades(first, last)
}

function durationBetweenTrades(current: BacktestTrade, next?: BacktestTrade): number | string {
  if (!next) return '-'
  const currentTime = klineData.value[current.pos]?.time
  const nextTime = klineData.value[next.pos]?.time
  if (typeof currentTime === 'number' && typeof nextTime === 'number') {
    return Math.max(Math.round((nextTime - currentTime) / 60), 0)
  }
  return Math.max(next.pos - current.pos, 0)
}

const tableRows = computed<TradeTableRow[]>(() => {
  const rows: TradeTableRow[] = []
  tradeRecords.value.forEach((record, recordIndex) => {
    const first = firstTrade(record)
    rows.push({
      key: `record-${recordIndex}-${first?.pos ?? 'empty'}`,
      kind: 'parent',
      record,
      recordIndex,
      trade: first
    })

    if (!expandedRecords.value.has(recordIndex)) return
    record.trades.slice(1).forEach((trade, childIndex) => {
      const tradeIndex = childIndex + 1
      rows.push({
        key: `record-${recordIndex}-trade-${tradeIndex}-${trade.pos}-${trade.behavior}`,
        kind: 'child',
        record,
        recordIndex,
        trade,
        nextTrade: record.trades[tradeIndex + 1],
        tradeIndex
      })
    })
  })
  return rows
})

function toggleRecord(index: number): void {
  const next = new Set(expandedRecords.value)
  if (next.has(index)) next.delete(index)
  else next.add(index)
  expandedRecords.value = next
}

function focusTrade(pos: number): void {
  chartRef.value?.focusTrade(pos)
}

async function focusFirstTrade(records: BacktestTradeRecord[]): Promise<void> {
  const firstPos = records.find((record) => record.trades.length)?.trades[0]?.pos
  if (firstPos === undefined) return
  await nextTick()
  focusTrade(firstPos)
}

async function handleBacktest(id: 1 | 2) {
  if (id === 2) {
    klineData.value = []
    tradeRecords.value = []
    backtestSummary.value = null
    expandedRecords.value = new Set()
    return
  }

  if (!selectedTask.value) return

  isRunning.value = true
  try {
    const response = await postMessage(eMsg.eBacktest, { id, selectedTask: selectedTask.value })
    const payload = response as BacktestPayload & { received?: { args?: BacktestPayload } }
    const result = payload.received?.args ?? payload
    const kLine = result?.kLine ?? []
    const records = normalizeTradeRecords(result?.tradeRecords)
    backtestSummary.value = (payload.summarize ?? result?.summarize ?? null) as Record<string, unknown> | null
    klineData.value = normalizeKline(kLine)
    tradeRecords.value = records
    expandedRecords.value = new Set()
    await focusFirstTrade(records)
  } finally {
    isRunning.value = false
  }
}

onMounted(() => {
  const pageData = inject<Ref<any>>('pageData')
  const list = pageData?.value as string[] | undefined
  taskList.value = list ?? []
  if (taskList.value.length)
    selectedTask.value = taskList.value[0]!
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
          <button @click="handleBacktest(1)" :disabled="isRunning" class="group flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
                   transition-all duration-150 select-none
                   bg-emerald-500 hover:bg-emerald-600 active:scale-95
                   text-white shadow-sm shadow-emerald-200
                   disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100">
            <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>

          </button>

          <!-- 刷新按钮 -->
          <button @click="handleBacktest(2)" class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
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

      <LightweightChart ref="chartRef" :data="klineData" :trade-records="tradeRecords" :height="400" />
    </div>

    <!-- 下单记录 / 回测结果 -->
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm flex-1 flex flex-col min-h-0">
      <!-- Tab 导航 -->
      <div class="flex items-center px-4 py-3 border-b border-gray-100 shrink-0 bg-white">
        <div class="inline-flex rounded-lg bg-slate-100 p-1 gap-1">
          <button v-for="tab in tabs" :key="tab.key" @click="activeTab = tab.key"
            class="relative px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-150 select-none" :class="activeTab === tab.key
              ? 'text-white bg-indigo-500 shadow-sm'
              : 'text-slate-500 bg-white hover:text-slate-700'">
            {{ tab.label }}
          </button>
        </div>
      </div>

      <!-- Tab 内容 -->
      <div class="flex-1 overflow-auto min-h-0">

        <!-- 下单记录 -->
        <template v-if="activeTab === 'orders'">
          <table class="w-full">
            <thead class="bg-gray-50 sticky top-0">
              <tr>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-400 uppercase tracking-wide">顺序</th>
                <th class="pl-8 pr-4 py-2.5 text-left text-xs font-semibold text-gray-400 uppercase tracking-wide">时间
                </th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-400 uppercase tracking-wide">持续时间(m)
                </th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-400 uppercase tracking-wide">类型</th>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-400 uppercase tracking-wide">方向</th>
                <th class="px-4 py-2.5 text-right text-xs font-semibold text-gray-400 uppercase tracking-wide">交易次数</th>
                <th class="px-4 py-2.5 text-right text-xs font-semibold text-gray-400 uppercase tracking-wide">杠杆</th>
                <th class="px-4 py-2.5 text-right text-xs font-semibold text-gray-400 uppercase tracking-wide">仓位%</th>
                <th class="px-4 py-2.5 text-right text-xs font-semibold text-gray-400 uppercase tracking-wide"></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50">
              <tr v-if="!tradeRecords.length">
                <td colspan="9" class="px-4 py-12 text-center text-sm text-gray-300">暂无交易轨迹</td>
              </tr>
              <tr v-for="row in tableRows" :key="row.key" :class="row.kind === 'child'
                ? 'bg-slate-200/80'
                : 'hover:bg-gray-50 transition-colors duration-75'">
                <td :class="row.kind === 'child'
                  ? 'pl-9 pr-4 py-2 text-xs font-mono text-gray-400'
                  : 'px-4 py-2.5 text-xs font-mono text-gray-500'">
                  {{ row.kind === 'parent' ? row.recordIndex + 1 : '' }}
                </td>
                <td :class="row.kind === 'child'
                  ? 'pl-[51px] pr-4 py-2 text-xs font-mono text-gray-500'
                  : 'pl-8 pr-4 py-2.5 text-xs font-mono text-gray-500'">
                  {{ formatTimeByPos(row.trade?.pos ?? -1) }}
                </td>
                <td :class="row.kind === 'child'
                  ? 'pl-9 pr-4 py-2 text-sm font-mono text-left text-gray-400'
                  : 'px-4 py-2.5 text-sm font-mono text-left text-gray-500'">
                  {{ row.kind === 'parent' ? durationMinutes(row.record) : durationBetweenTrades(row.trade!,
                    row.nextTrade) }}
                </td>
                <td :class="row.kind === 'child'
                  ? 'pl-9 pr-4 py-2 text-sm text-gray-500'
                  : 'px-4 py-2.5 text-sm font-medium text-gray-800'">
                  {{ row.kind === 'parent' ? row.record.type : '-' }}
                </td>
                <td :class="row.kind === 'child'
                  ? 'pl-9 pr-4 py-2 text-sm font-mono text-gray-600'
                  : 'px-4 py-2.5 text-sm font-mono text-gray-700'">
                  {{ directionText(row.record, row.trade) }}
                </td>
                <td :class="row.kind === 'child'
                  ? 'pl-9 pr-4 py-2 text-sm font-mono text-right text-gray-400'
                  : 'px-4 py-2.5 text-sm font-mono text-right text-gray-800'">
                  {{ row.kind === 'parent' ? row.record.trades.length : '-' }}
                </td>
                <td :class="row.kind === 'child'
                  ? 'pl-9 pr-4 py-2 text-sm font-mono text-right text-gray-500'
                  : 'px-4 py-2.5 text-sm font-mono text-right text-gray-500'">
                  {{ row.trade?.lv ?? '-' }}
                </td>
                <td :class="row.kind === 'child'
                  ? 'pl-9 pr-4 py-2 text-sm font-mono text-right text-gray-500'
                  : 'px-4 py-2.5 text-sm font-mono text-right text-gray-500'">
                  {{ row.trade?.['position%'] ?? '-' }}
                </td>
                <td class="px-4 py-2.5 text-right">
                  <template v-if="row.kind === 'parent'">
                    <div class="flex items-center justify-end gap-2">
                      <button
                        class="px-2.5 py-1 rounded-md text-xs font-semibold text-indigo-600 bg-indigo-50 hover:bg-indigo-100"
                        @click="focusTrade(row.trade?.pos ?? 0)">
                        追踪
                      </button>
                      <button
                        class="min-w-9 px-2.5 py-1 rounded-md text-xs font-semibold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 inline-flex items-center justify-center"
                        @click="toggleRecord(row.recordIndex)">
                        {{ expandedRecords.has(row.recordIndex) ? '^' : 'v' }}
                      </button>
                    </div>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </template>

        <!-- 回测结果 -->
        <template v-else>
          <div v-if="backtestSummary" class="p-4 space-y-4">
            <div class="grid grid-cols-2 xl:grid-cols-4 gap-3">
              <div v-for="metric in summaryHighlights" :key="metric.path" :class="summaryCardClass(metric, metric.raw)">
                <span class="text-xs text-slate-400 font-medium">{{ metric.label }}</span>
                <span :class="['text-2xl font-bold font-mono leading-none', summaryValueClass(metric, metric.raw)]">
                  {{ metric.value }}<span v-if="metric.unit" class="text-sm font-normal ml-0.5">{{ metric.unit }}</span>
                </span>
              </div>
            </div>

            <div v-for="section in summarySections" :key="section.title" class="rounded-xl border border-gray-100 bg-white">
              <div class="flex items-center justify-between px-4 pt-4 pb-3">
                <h3 class="text-sm font-semibold text-slate-700">{{ section.title }}</h3>
                <span class="text-xs text-slate-400">{{ section.metrics.length }}项</span>
              </div>
              <div class="grid grid-cols-2 xl:grid-cols-3 gap-3 px-4 pb-4">
                <div v-for="metric in section.metrics" :key="metric.path" :class="summaryCardClass(metric, metric.raw)">
                  <span class="text-xs text-slate-400 font-medium">{{ metric.label }}</span>
                  <span :class="['text-lg font-bold font-mono leading-none', summaryValueClass(metric, metric.raw)]">
                    {{ metric.value }}<span v-if="metric.unit" class="text-sm font-normal ml-0.5">{{ metric.unit }}</span>
                  </span>
                </div>
              </div>
            </div>

            <div v-if="scoreDetails.length" class="rounded-xl border border-gray-100 bg-white p-4">
              <div class="flex items-center justify-between mb-3">
                <h3 class="text-sm font-semibold text-slate-700">评分说明</h3>
                <span class="text-xs text-slate-400">{{ scoreDetails.length }}条</span>
              </div>
              <div class="space-y-2">
                <div v-for="(detail, index) in scoreDetails" :key="`${index}-${detail}`"
                  class="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
                  {{ detail }}
                </div>
              </div>
            </div>
          </div>
          <div v-else class="p-8 text-center text-sm text-gray-300">
            暂无回测结果
          </div>
        </template>

      </div>
    </div>

  </div>
</template>
