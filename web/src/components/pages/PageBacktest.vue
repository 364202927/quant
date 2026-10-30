<script setup lang="ts">
import { computed, ref, inject, nextTick, onActivated, onDeactivated, onMounted, watch, type Ref } from 'vue'
import LightweightChart from '../../utils/LightweightChart.vue'
import { eMsg, type BacktestTrade, type BacktestTradeRecord, type CandlestickData } from '../../types'
import { postMessage } from '../../utils/common'
import { detectKlinePeriod, type KlinePeriod } from '../../utils/kline'
import { useSimBacktest } from '../../utils/simBacktest'

const SIM_TASK = '__sim__'

const klineData = ref<CandlestickData[]>([])
const tradeRecords = ref<BacktestTradeRecord[]>([])
const backtestSummary = ref<Record<string, unknown> | null>(null)
const expandedRecords = ref<Set<number>>(new Set())
const chartRef = ref<InstanceType<typeof LightweightChart> | null>(null)
const activeTab = ref<'orders' | 'results'>('orders')
const isRunning = ref(false)
const isolateData = ref(true)
const errorMessage = ref('')
const isSimLoading = ref(false)
const isPlaying = ref(false)
let playTimer: number | null = null
const chartPeriod = ref<KlinePeriod>('5m')
const sim = useSimBacktest(chartPeriod)
const {
  symbol: simSymbol,
  principalModel: simPrincipal,
  bet: simBet,
  lv: simLv,
  started: simStarted,
  hasMore: simHasMore,
  displayBars: simDisplayBars,
  tradeRecords: simTradeRecords,
} = sim

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
  { label: '盈利因子', path: 'return_quality.profit_factor', digits: 4, tone: 'profit', important: true },
]

const summaryGroupConfigs: { title: string; metrics: SummaryMetricConfig[] }[] = [
  {
    title: '基础',
    metrics: [
      { label: '初始本金', path: 'basic.initial_principal' },
      { label: '起始权益', path: 'basic.initial_equity' },
      { label: '期末权益', path: 'basic.margin' },
      { label: '平均杠杆', path: 'basic.leverage', unit: 'x' },
      { label: '总交易', path: 'basic.n_trades', unit: '次' },
      { label: '交易日', path: 'basic.trading_days', unit: '天' },
      { label: '手续费', path: 'basic.total_trade_fee', tone: 'risk' },
      { label: '滑点成本', path: 'basic.total_slippage_cost', tone: 'risk' },
      { label: '资金费', path: 'basic.total_funding_fee', tone: 'risk' },
      { label: '放弃开仓', path: 'basic.skipped_opens', unit: '次' },
      { label: '爆仓', path: 'basic.blowup' },
    ]
  },
  {
    title: '收益',
    metrics: [
      { label: '年化收益', path: 'return_quality.cagr_pct', unit: '%', tone: 'profit' },
      { label: '总收益', path: 'return_quality.total_return_pct', unit: '%', tone: 'profit' },
      { label: '盈亏比', path: 'return_quality.win_loss_ratio', digits: 4, tone: 'profit' },
      { label: '盈利因子', path: 'return_quality.profit_factor', digits: 4, tone: 'profit' },
      { label: '去极值利润', path: 'return_quality.trimmed_profit', tone: 'profit' },
    ]
  },
  {
    title: '风险',
    metrics: [
      { label: '最大回撤', path: 'live_tolerance.max_drawdown_pct', unit: '%', tone: 'risk' },
      { label: '日波动率', path: 'post_cost_survival.daily_volatility', digits: 6, tone: 'risk' },
      { label: '年化波动率', path: 'post_cost_survival.annual_volatility', digits: 4, tone: 'risk' },
      { label: '日CVaR95', path: 'post_cost_survival.cvar_95_pct', unit: '%', tone: 'risk' },
      { label: '最大占用保证金', path: 'live_tolerance.max_margin_used' },
      { label: '年化换手', path: 'live_tolerance.turnover_rate_annual', digits: 4, tone: 'risk' },
    ]
  },
  {
    title: '稳健',
    metrics: [
      { label: '夏普', path: 'overfit_filter.sharpe_ratio', digits: 4, tone: 'profit' },
      { label: '卡玛', path: 'overfit_filter.calmar_ratio', digits: 4, tone: 'profit' },
      { label: 'DSR P值', path: 'overfit_filter.deflated_sharpe_pvalue', digits: 4 },
      { label: '后半段夏普变化', path: 'live_tolerance.oos_sharpe_change', digits: 4 },
      { label: '成本盈亏平衡', path: 'live_tolerance.cost_breakeven_multiple', unit: 'x', digits: 4 },
      { label: '2倍成本利润', path: 'live_tolerance.stress_2x_cost_profit', tone: 'profit' },
    ]
  }
]

// inject 必须在 setup 顶层
const taskList = ref<string[]>([])
const selectedTask = ref<string>('')
const simMode = computed(() => selectedTask.value === SIM_TASK)
const chartData = computed(() => (simMode.value ? simDisplayBars.value : klineData.value))
const chartTrades = computed(() => (simMode.value ? simTradeRecords.value : tradeRecords.value))

type KlineRow = Partial<CandlestickData> & {
  vol?: number | null
  [key: string]: unknown
}

interface BacktestPayload {
  kLine?: KlineRow[]
  pf?: KlineRow[]
  tradeRecords?: BacktestTradeRecord[]
  summarize?: Record<string, unknown>
  error?: string
}

type TradeTableRow = {
  key: string
  child: boolean
  recordIndex: number
  trade?: BacktestTrade
  sequence: string
  time: string
  duration: number | string
  type: string
  direction: string
  count: number | string
  level: number | string
  position: number | string
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
  const neutral = important ? 'text-slate-900' : 'text-slate-700'

  if (config.path === 'basic.blowup') return raw ? 'text-rose-600' : 'text-emerald-600'

  if (typeof raw === 'string') {
    if (tone !== 'verdict') return neutral
    if (raw.includes('可实盘')) return 'text-emerald-600'
    if (raw.includes('继续改善')) return 'text-amber-600'
    return 'text-rose-600'
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

  if (config.path === 'live_tolerance.oos_sharpe_change') {
    if (num >= -0.3) return 'text-emerald-600'
    if (num >= -0.5) return 'text-amber-600'
    return 'text-rose-600'
  }

  if (tone === 'profit') return num >= 0 ? 'text-emerald-600' : 'text-rose-600'
  if (tone === 'risk') return num <= 0 ? 'text-emerald-600' : 'text-rose-600'
  return neutral
}

function summaryCardClass(config: SummaryMetricConfig, raw: unknown): string {
  const important = config.important
  const tone = summaryValueClass(config, raw)
  return [
    'rounded-lg border px-4 py-3 flex flex-col gap-1',
    important ? 'bg-paper border-paper-line' : 'bg-paper-deep/40 border-paper-line/70',
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

    const fundingBps = toNumber(item.funding_bps ?? item.fundingBps)
    if (fundingBps !== null)
      bar.fundingBps = fundingBps

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
  const time = chartData.value[pos]?.time
  if (time === undefined) return '-'
  if (typeof time === 'number') {
    return new Date(time * 1000).toLocaleString()
  }
  return String(time)
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
  const currentTime = chartData.value[current.pos]?.time
  const nextTime = chartData.value[next.pos]?.time
  if (typeof currentTime === 'number' && typeof nextTime === 'number') {
    return Math.max(Math.round((nextTime - currentTime) / 60), 0)
  }
  return Math.max(next.pos - current.pos, 0)
}

function buildParentRow(record: BacktestTradeRecord, recordIndex: number): TradeTableRow {
  const trade = record.trades[0]
  return {
    key: `record-${recordIndex}`,
    child: false,
    recordIndex,
    trade,
    sequence: String(recordIndex + 1),
    time: formatTimeByPos(trade?.pos ?? -1),
    duration: durationMinutes(record),
    type: record.type,
    direction: directionText(record, trade),
    count: record.trades.length,
    level: trade?.lv ?? '-',
    position: trade?.['position%'] ?? '-'
  }
}

function buildChildRow(record: BacktestTradeRecord, recordIndex: number, tradeIndex: number): TradeTableRow {
  const trade = record.trades[tradeIndex]!
  return {
    key: `record-${recordIndex}-trade-${tradeIndex}`,
    child: true,
    recordIndex,
    trade,
    sequence: `${recordIndex + 1}.${tradeIndex + 1}`,
    time: formatTimeByPos(trade.pos),
    duration: durationBetweenTrades(trade, record.trades[tradeIndex + 1]),
    type: '-',
    direction: directionText(record, trade),
    count: '-',
    level: trade.lv,
    position: trade['position%']
  }
}

const tableRows = computed<TradeTableRow[]>(() => chartTrades.value.flatMap((record, recordIndex) => {
  const rows = [buildParentRow(record, recordIndex)]
  if (!expandedRecords.value.has(recordIndex)) return rows

  record.trades.slice(1).forEach((_, offset) => {
    rows.push(buildChildRow(record, recordIndex, offset + 1))
  })
  return rows
}))

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

const busy = computed(() => (simMode.value ? isSimLoading.value : isRunning.value))
const cancelMode = computed(() => simMode.value && simStarted.value)
const primaryLabel = computed(() => {
  if (simMode.value) {
    if (isSimLoading.value) return '加载中…'
    return simStarted.value ? '取消测试' : '开始回测'
  }
  return isRunning.value ? '回测中…' : '开始回测'
})
const busyTitle = computed(() => (simMode.value ? '正在加载 K 线数据…' : '回测运行中…'))
const busyHint = computed(() => {
  if (simMode.value)
    return `${simSymbol.value.trim() || 'symbol'} · 随机截取约 1 年 5m K 线`
  return isolateData.value
    ? '数据隔离模式：逐段揭示 K 线，跑完整段后返回'
    : '快速回测：全量一次计算'
})

async function focusSimLast(fitPrice = false): Promise<void> {
  if (!simDisplayBars.value.length) return
  await nextTick()
  chartRef.value?.scrollToLast(80, fitPrice)
}

const playbackLabel = computed(() => {
  if (!simHasMore.value) return '已播完'
  return isPlaying.value ? '播放中' : '已暂停'
})

function stopPlayback(): void {
  if (playTimer !== null) {
    window.clearInterval(playTimer)
    playTimer = null
  }
  isPlaying.value = false
}

function startPlayback(): void {
  if (!simStarted.value || !simHasMore.value || playTimer !== null) return
  isPlaying.value = true
  playTimer = window.setInterval(tickPlayback, 1000)
}

function tickPlayback(): void {
  if (!simMode.value || !simStarted.value || !sim.play()) {
    stopPlayback()
    return
  }
  void focusSimLast()
}

// 空格：播放中停止，停止后再按继续
function togglePlayback(): void {
  if (isPlaying.value) {
    stopPlayback()
    return
  }
  startPlayback()
}

function handlePlaybackToggle(event: MouseEvent): void {
  togglePlayback()
  ;(event.currentTarget as HTMLElement | null)?.blur()
}

async function runTaskBacktest(): Promise<void> {
  if (!selectedTask.value || simMode.value) return

  isRunning.value = true
  errorMessage.value = ''
  try {
    const response = await postMessage(eMsg.eBacktest, {
      id: isolateData.value ? 0 : 1,
      selectedTask: selectedTask.value
    })
    const payload = response as BacktestPayload & { received?: { args?: BacktestPayload } }
    const result = payload.received?.args ?? payload
    if (result?.error) {
      errorMessage.value = result.error
      return
    }
    const kLine = result?.kLine ?? []
    const records = normalizeTradeRecords(result?.tradeRecords)
    backtestSummary.value = (payload.summarize ?? result?.summarize ?? null) as Record<string, unknown> | null
    klineData.value = normalizeKline(kLine)
    tradeRecords.value = records
    expandedRecords.value = new Set()
    chartPeriod.value = detectKlinePeriod(klineData.value)
    await focusFirstTrade(records)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    isRunning.value = false
  }
}

function clearTaskBacktest(): void {
  klineData.value = []
  tradeRecords.value = []
  backtestSummary.value = null
  expandedRecords.value = new Set()
  errorMessage.value = ''
}

async function startSim(): Promise<void> {
  const name = simSymbol.value.trim() || 'binance_swap_BTCUSDT'
  simSymbol.value = name
  if (sim.principal.value <= 0 || sim.bet.value <= 0 || sim.bet.value > 100 || sim.lv.value < 1) {
    errorMessage.value = '请检查本金 / 下注% / lv'
    return
  }

  isSimLoading.value = true
  errorMessage.value = ''
  ;(document.activeElement as HTMLElement | null)?.blur()
  try {
    const response = await postMessage(eMsg.eBacktest, { id: name })
    const payload = response as BacktestPayload & { received?: { args?: BacktestPayload } }
    const result = payload.received?.args ?? payload
    if (result?.error) {
      errorMessage.value = result.error
      return
    }
    const bars = normalizeKline(result?.kLine ?? [])
    if (!bars.length) {
      errorMessage.value = '未获取到K线数据'
      return
    }
    sim.start(bars)
    await focusSimLast(true)
    startPlayback()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    isSimLoading.value = false
  }
}

function handlePrimaryAction(): void {
  if (simMode.value) {
    if (simStarted.value) {
      stopPlayback()
      sim.cancelTest()
      ;(document.activeElement as HTMLElement | null)?.blur()
      return
    }
    void startSim()
    return
  }
  void runTaskBacktest()
}

function handleSimKey(event: KeyboardEvent): void {
  if (!simMode.value || !simStarted.value || isSimLoading.value) return
  const target = event.target as HTMLElement | null
  if (
    target &&
    (target.isContentEditable ||
      ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))
  )
    return
  switch (event.key) {
    case ' ':
    case 'Spacebar':
      event.preventDefault()
      if (event.repeat) return
      togglePlayback()
      return
    case 'l':
    case 'L':
      sim.openLong()
      return
    case 's':
    case 'S':
      sim.openShort()
      return
    case 'c':
    case 'C':
      sim.close()
      return
    case 'Escape':
      sim.undo()
  }
}

watch(selectedTask, (value, oldValue) => {
  stopPlayback()
  if (value === SIM_TASK) {
    clearTaskBacktest()
    sim.cancelTest()
    activeTab.value = 'orders'
    return
  }
  if (oldValue === SIM_TASK) sim.cancelTest()
})

watch(chartPeriod, () => {
  if (simMode.value && simStarted.value) void focusSimLast()
})

onActivated(() => {
  window.addEventListener('keydown', handleSimKey)
})

onDeactivated(() => {
  stopPlayback()
  window.removeEventListener('keydown', handleSimKey)
})

onMounted(() => {
  const pageData = inject<Ref<any>>('pageData')
  const list = pageData?.value as string[] | undefined
  taskList.value = list ?? []
  if (taskList.value.length)
    selectedTask.value = taskList.value[0]!
})
</script>

<template>
  <div class="page-body flex flex-col gap-3 overflow-hidden">

    <!-- K线图区域 -->
    <div class="panel shrink-0 p-4">
      <!-- 实例选择栏 -->
      <div class="flex flex-wrap items-center gap-3 mb-3">
        <span class="text-xs font-semibold text-ink-faint uppercase tracking-widest whitespace-nowrap">实例</span>

        <!-- 实例下拉 -->
        <div class="relative min-w-40 flex-1 max-w-56">
          <select v-model="selectedTask" :disabled="isRunning || isSimLoading" class="w-full appearance-none bg-paper border border-paper-line rounded-lg
                   pl-3 pr-8 py-1.5 text-sm font-medium text-ink
                   focus:outline-none focus:ring-2 focus:ring-indigo-400/40 focus:border-transparent
                   transition-all cursor-pointer disabled:cursor-not-allowed disabled:opacity-60">
            <option v-if="!taskList.length" value="" disabled>暂无实例</option>
            <option v-for="task in taskList" :key="task" :value="task">{{ task }}</option>
            <option :value="SIM_TASK">模拟回测</option>
          </select>
          <svg class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-ink-faint"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>

        <!-- 操作按钮组 -->
        <div class="ml-auto flex flex-wrap items-center justify-end gap-2">
          <!-- 模拟回测参数 -->
          <div class="flex flex-wrap items-center gap-1.5" :style="{ display: simMode ? 'flex' : 'none' }">
            <label class="flex items-center gap-1 text-[11px] font-medium text-ink-soft">
              <span>symbol</span>
              <input v-model="simSymbol" :readonly="simStarted" type="text" placeholder="binance_swap_BTCUSDT"
                class="w-44 rounded border border-paper-line bg-paper px-2 py-1 text-xs text-ink focus:outline-none focus:ring-1 focus:ring-indigo-400/40 read-only:bg-paper-deep/40" />
            </label>
            <label class="flex items-center gap-1 text-[11px] font-medium text-ink-soft">
              <span>本金</span>
              <input v-model.number="simPrincipal" :readonly="simStarted" type="number" min="1" step="100"
                class="w-20 rounded border border-paper-line bg-paper px-2 py-1 text-xs text-ink focus:outline-none focus:ring-1 focus:ring-indigo-400/40 read-only:bg-paper-deep/40" />
            </label>
            <label class="flex items-center gap-1 text-[11px] font-medium text-ink-soft">
              <span>下注%</span>
              <input v-model.number="simBet" type="number" min="1" max="100" step="1"
                title="开仓保证金占权益的百分比；平仓按该百分比减仓，100% 全平；手续费 0.05%/边"
                class="w-16 rounded border border-paper-line bg-paper px-2 py-1 text-xs text-ink focus:outline-none focus:ring-1 focus:ring-indigo-400/40" />
            </label>
            <label class="flex items-center gap-1 text-[11px] font-medium text-ink-soft">
              <span>lv</span>
              <input v-model.number="simLv" type="number" min="1" step="1"
                class="w-14 rounded border border-paper-line bg-paper px-2 py-1 text-xs text-ink focus:outline-none focus:ring-1 focus:ring-indigo-400/40" />
            </label>
            <button v-if="simStarted" type="button" @click="handlePlaybackToggle"
              class="cursor-pointer rounded-full border px-2 py-0.5 text-[11px] font-medium transition-colors"
              :class="isPlaying
                ? 'border-emerald-200 bg-emerald-50 text-emerald-600'
                : 'border-amber-200 bg-amber-50 text-amber-600'"
              title="空格暂停/继续，每秒新增一根 K 线">
              {{ playbackLabel }}
            </button>
          </div>

          <!-- 数据隔离开关 -->
          <label class="mr-1 flex items-center gap-1.5 text-xs font-medium text-ink-soft select-none cursor-pointer"
            :style="{ display: simMode ? 'none' : 'flex' }"
            :title="isolateData ? '数据隔离：逐根揭示K线回放，跑完整段才返回' : '快速回测：全量一次计算'">
            <input v-model="isolateData" type="checkbox" :disabled="isRunning"
              class="h-3.5 w-3.5 accent-indigo-600 cursor-pointer disabled:cursor-not-allowed" />
            数据隔离
          </label>

          <!-- 开始回测 / 取消测试 -->
          <button @click="handlePrimaryAction" :disabled="busy" :title="cancelMode ? '取消测试' : '开始回测'" class="group flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold
                   transition-all duration-150 select-none
                   active:scale-95
                   disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100"
            :class="cancelMode
              ? 'bg-rose-600 hover:bg-rose-700 text-white shadow-sm shadow-rose-200/50'
              : 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm shadow-emerald-200/50'">
            <svg v-if="cancelMode" class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="1" />
            </svg>
            <svg v-else class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>
            {{ primaryLabel }}
          </button>

          <!-- 清空按钮 -->
          <button @click="clearTaskBacktest" title="清空回测结果" :style="{ display: simMode ? 'none' : 'flex' }" class="items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
                   border border-paper-line bg-paper text-ink-soft
                   hover:bg-paper-deep hover:text-ink
                   active:scale-95 transition-all duration-150">
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            清空
          </button>
        </div>
      </div>

      <LightweightChart ref="chartRef" v-model:period="chartPeriod" :data="chartData" :trade-records="chartTrades"
        :auto-price-range="!simMode" :height="360" />
    </div>

    <!-- 下单记录 / 回测结果 -->
    <div class="panel flex-1 flex flex-col min-h-0">
      <!-- Tab 导航 -->
      <div class="flex items-center gap-3 px-4 py-3 border-b border-paper-line shrink-0">
        <div class="inline-flex rounded-lg bg-paper-deep p-1 gap-1">
          <button v-for="tab in tabs" :key="tab.key" @click="activeTab = tab.key"
            class="relative px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-150 select-none" :class="activeTab === tab.key
              ? 'text-white bg-indigo-600 shadow-sm'
              : 'text-ink-soft bg-paper-soft hover:text-ink'">
            {{ tab.label }}
          </button>
        </div>
        <p v-if="errorMessage" class="ml-auto truncate text-xs font-medium text-rose-600" :title="errorMessage">
          {{ errorMessage }}
        </p>
      </div>

      <!-- Tab 内容 -->
      <div class="flex-1 overflow-auto min-h-0 [scrollbar-gutter:stable]">

        <!-- 下单记录 -->
        <template v-if="activeTab === 'orders'">
          <table class="w-full min-w-[980px] table-fixed">
            <colgroup>
              <col class="w-[76px]" />
              <col class="w-[176px]" />
              <col class="w-[112px]" />
              <col class="w-[96px]" />
              <col class="w-[128px]" />
              <col class="w-[88px]" />
              <col class="w-[72px]" />
              <col class="w-[88px]" />
              <col class="w-[140px]" />
            </colgroup>
            <thead class="bg-paper-deep/70 sticky top-0 z-10 backdrop-blur">
              <tr>
                <th class="px-3 py-2.5 text-left text-xs font-semibold text-gray-400 uppercase tracking-wide">顺序</th>
                <th class="px-3 py-2.5 text-left text-xs font-semibold text-gray-400 uppercase tracking-wide">时间</th>
                <th class="px-3 py-2.5 text-left text-xs font-semibold text-gray-400 uppercase tracking-wide">持续时间(m)
                </th>
                <th class="px-3 py-2.5 text-left text-xs font-semibold text-gray-400 uppercase tracking-wide">类型</th>
                <th class="px-3 py-2.5 text-left text-xs font-semibold text-gray-400 uppercase tracking-wide">方向</th>
                <th class="px-3 py-2.5 text-right text-xs font-semibold text-gray-400 uppercase tracking-wide">交易次数</th>
                <th class="px-3 py-2.5 text-right text-xs font-semibold text-gray-400 uppercase tracking-wide">杠杆</th>
                <th class="px-3 py-2.5 text-right text-xs font-semibold text-gray-400 uppercase tracking-wide">仓位%</th>
                <th class="px-3 py-2.5 text-right text-xs font-semibold text-gray-400 uppercase tracking-wide">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50">
              <tr v-if="!chartTrades.length">
                <td colspan="9" class="px-4 py-12 text-center text-sm text-gray-300">暂无交易轨迹</td>
              </tr>
              <tr v-for="row in tableRows" :key="row.key"
                :class="row.child ? 'bg-paper-deep/60' : 'hover:bg-gray-50 transition-colors duration-75'">
                <td class="px-3 py-2.5 text-left text-xs font-mono whitespace-nowrap"
                  :class="row.child ? 'text-gray-400' : 'text-gray-600 font-medium'">
                  {{ row.sequence }}
                </td>
                <td class="px-3 py-2.5 text-left text-xs font-mono text-gray-500 truncate" :title="row.time">{{ row.time }}</td>
                <td class="px-3 py-2.5 text-left text-xs font-mono text-gray-500 whitespace-nowrap">{{ row.duration }}</td>
                <td class="px-3 py-2.5 text-left text-xs whitespace-nowrap"
                  :class="row.child ? 'text-gray-500' : 'text-gray-700 font-medium'">
                  {{ row.type }}
                </td>
                <td class="px-3 py-2.5 text-left text-xs font-mono text-gray-600 whitespace-nowrap">{{ row.direction }}</td>
                <td class="px-3 py-2.5 text-right text-xs font-mono text-gray-600 whitespace-nowrap">{{ row.count }}</td>
                <td class="px-3 py-2.5 text-right text-xs font-mono text-gray-500 whitespace-nowrap">{{ row.level }}</td>
                <td class="px-3 py-2.5 text-right text-xs font-mono text-gray-500 whitespace-nowrap">{{ row.position }}</td>
                <td class="px-3 py-2.5 text-right">
                  <div v-if="!row.child" class="flex items-center justify-end gap-2">
                    <button
                      class="px-2.5 py-1 rounded-md text-xs font-semibold text-indigo-600 bg-indigo-50 hover:bg-indigo-100"
                      @click="focusTrade(row.trade?.pos ?? 0)">
                      追踪
                    </button>
                    <button
                      class="min-w-9 px-2.5 py-1 rounded-md text-xs font-semibold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 inline-flex items-center justify-center"
                      :aria-expanded="expandedRecords.has(row.recordIndex)"
                      :title="expandedRecords.has(row.recordIndex) ? '收起成交明细' : '展开成交明细'"
                      @click="toggleRecord(row.recordIndex)">
                      {{ expandedRecords.has(row.recordIndex) ? '^' : 'v' }}
                    </button>
                  </div>
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

            <div v-for="section in summarySections" :key="section.title" class="rounded-xl border border-paper-line bg-paper-soft">
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

            <div v-if="scoreDetails.length" class="rounded-xl border border-paper-line bg-paper-soft p-4">
              <div class="flex items-center justify-between mb-3">
                <h3 class="text-sm font-semibold text-slate-700">评分说明</h3>
                <span class="text-xs text-slate-400">{{ scoreDetails.length }}条</span>
              </div>
              <div class="space-y-2">
                <div v-for="(detail, index) in scoreDetails" :key="`${index}-${detail}`"
                  class="rounded-lg bg-paper px-3 py-2 text-sm text-ink-soft">
                  {{ detail }}
                </div>
              </div>
            </div>
          </div>
          <div v-else class="p-8 text-center text-sm text-ink-faint">
            暂无回测结果
          </div>
        </template>

      </div>
    </div>

    <!-- 回测/取数进行中的遮罩：拦截全部点击，避免加载期间误操作 -->
    <div v-if="busy" class="fixed inset-0 z-50 flex items-center justify-center bg-ink/20 backdrop-blur-sm cursor-wait">
      <div class="flex flex-col items-center gap-2 rounded-xl border border-paper-line bg-paper-soft px-8 py-6 shadow-2xl">
        <i class="ri-loader-4-line animate-spin text-2xl text-indigo-600"></i>
        <p class="text-sm font-semibold text-ink">{{ busyTitle }}</p>
        <p class="text-xs text-ink-faint">{{ busyHint }}</p>
      </div>
    </div>

  </div>
</template>
