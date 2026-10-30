<script lang="ts">
import { defineComponent } from "vue";

export default defineComponent({
  name: "LightweightChart",
});
</script>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch } from "vue";
import {
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  type HistogramData,
  type IChartApi,
  type ISeriesMarkersPluginApi,
  type ISeriesApi,
  type CandlestickData as LWCandlestickData,
  type LineData,
  type SeriesMarker,
  type Time,
  CrosshairMode,
} from "lightweight-charts";
import { DrawingManager } from "lightweight-charts-drawing";
import type { DrawingKind, OHLC } from "lightweight-charts-drawing";
import type { BacktestTradeRecord, CandlestickData } from "../types";
import {
  bucketStart,
  periodOptions,
  resampleKline,
  type KlinePeriod,
} from "./kline";

interface Props {
  data: CandlestickData[];
  tradeRecords?: BacktestTradeRecord[];
  period?: KlinePeriod;
  width?: number;
  height?: number;
  autosize?: boolean;
  fill?: boolean;
  autoPriceRange?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  tradeRecords: () => [],
  width: 600,
  height: 400,
  autosize: true,
  fill: false,
  autoPriceRange: true,
});

const emit = defineEmits<{
  crosshairMove: [param: { time: Time; price: number } | null];
  click: [param: { time: Time; price: number }];
  "update:period": [value: KlinePeriod];
}>();

const chartContainer = ref<HTMLDivElement | null>(null);
const hoveredBar = ref<CandlestickData | null>(null);
const innerPeriod = ref<KlinePeriod>("5m");
const activePeriod = computed<KlinePeriod>(
  () => props.period ?? innerPeriod.value,
);
const displayData = computed(() =>
  resampleKline(props.data, activePeriod.value),
);
const displayIndexByTime = computed(() => {
  const result = new Map<number, number>();
  displayData.value.forEach((bar, index) => {
    const seconds = timeToSeconds(bar.time);
    if (seconds !== null) result.set(seconds, index);
  });
  return result;
});
let chart: IChartApi | null = null;
let candlestickSeries: ISeriesApi<"Candlestick"> | null = null;
let volumeSeries: ISeriesApi<"Histogram"> | null = null;
let vwapSeries: ISeriesApi<"Line"> | null = null;
let tradeMarkers: ISeriesMarkersPluginApi<Time> | null = null;

// --- 绘图工具状态 ---
let drawingManager: DrawingManager | null = null;
const activeTool = ref<DrawingKind | null>(null);

let dragState: {
  pointerId: number;
  startX: number;
  startY: number;
  startLogicalRange: { from: number; to: number } | null;
  startPriceRange: { from: number; to: number } | null;
  priceHeight: number;
} | null = null;

const priceFloor = 0;
let priceClampFrame = 0;
let priceClampTimer = 0;

// --- 绘图工具列表（对应你截图中的工具） ---
interface DrawingTool {
  kind: DrawingKind;
  label: string;
  title: string;
}

const drawingTools: DrawingTool[] = [
  { kind: "horizontal-line", label: "H", title: "水平线" },
  { kind: "trend-line", label: "T", title: "趋势线" },
  { kind: "parallel-channel", label: "C", title: "平行通道" },
  { kind: "fib-retracement", label: "F", title: "斐波那契回撤" },
  { kind: "rectangle", label: "R", title: "矩形" },
  {
    kind: "fixed-range-volume-profile",
    label: "VP",
    title: "固定成交量分布图",
  },
];

// --- 辅助函数 ---
function isValidNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function clampPriceRange(range: { from: number; to: number }): {
  from: number;
  to: number;
} {
  if (range.from >= priceFloor) return range;
  return { from: priceFloor, to: range.to + priceFloor - range.from };
}

function applyPriceRange(range: { from: number; to: number }): void {
  if (!chart) return;
  chart.priceScale("right").setVisibleRange(clampPriceRange(range));
}

function clampPriceScale(): void {
  const range = chart?.priceScale("right").getVisibleRange();
  if (range && range.from < priceFloor) applyPriceRange(range);
}

function schedulePriceClamp(): void {
  if (!priceClampFrame) {
    priceClampFrame = requestAnimationFrame(() => {
      priceClampFrame = 0;
      clampPriceScale();
    });
  }
  window.clearTimeout(priceClampTimer);
  priceClampTimer = window.setTimeout(clampPriceScale, 60);
}

function volumeValue(bar: CandlestickData): number | null {
  const value = bar.volume;
  return isValidNumber(value) ? value : null;
}

function vwapValue(bar: CandlestickData): number | null {
  const value = bar.vwap;
  return isValidNumber(value) ? value : null;
}

// 成交量分布图按 volume 分箱，K 线 series 自身不带成交量，需单独提供给绘图管理器
let drawingBarsSource: CandlestickData[] | null = null;
let drawingBarsCache: OHLC[] = [];

function drawingBars(): OHLC[] {
  const data = displayData.value;
  if (drawingBarsSource === data) return drawingBarsCache;
  drawingBarsSource = data;
  drawingBarsCache = data.map((bar) => ({
    time: bar.time as Time,
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: volumeValue(bar) ?? 0,
  }));
  return drawingBarsCache;
}

function markerText(
  index: number,
  dir: string,
  behavior: string,
  lv: number,
  position: number,
): string {
  const dirKey = dir ? dir.charAt(0).toLowerCase() : "";
  const behaviorKey = behavior ? behavior.charAt(0).toLowerCase() : "";
  return `(${index})${dirKey}${behaviorKey}_lv:${lv}_${position}%`;
}

function isTopTradeMarker(dir: string, behavior: string): boolean {
  if (!dir) return behavior === "buy";
  return (
    (dir === "SHORT" && behavior === "sell") ||
    (dir === "LONG" && behavior === "buy")
  );
}

function timeToSeconds(time: CandlestickData["time"] | Time): number | null {
  if (typeof time === "number" && Number.isFinite(time)) return time;
  const parsed = Date.parse(String(time));
  return Number.isFinite(parsed) ? parsed / 1000 : null;
}

function formatIndicatorValue(value: number | null | undefined): string {
  if (!isValidNumber(value)) return "--";
  if (Math.abs(value) >= 1000) return value.toFixed(2);
  if (Math.abs(value) >= 1) return value.toFixed(4);
  return value.toFixed(6);
}

function resolveBarByTime(time: Time): CandlestickData | null {
  const target = timeToSeconds(time);
  if (target === null) return null;
  const bars = displayData.value;
  let left = 0;
  let right = bars.length - 1;
  while (left <= right) {
    const mid = Math.floor((left + right) / 2);
    const bar = bars[mid];
    if (!bar) return null;
    const barTime = timeToSeconds(bar.time);
    if (barTime === null) return null;
    if (barTime === target) return bar;
    if (barTime < target) left = mid + 1;
    else right = mid - 1;
  }
  return null;
}

function latestBar(): CandlestickData | null {
  const bars = displayData.value;
  return bars.length ? (bars[bars.length - 1] ?? null) : null;
}

const periodLabel = computed(() => {
  if (props.period) {
    const option = periodOptions.find((item) => item.value === props.period);
    return option?.label ?? props.period;
  }
  const option = periodOptions.find((item) => item.value === activePeriod.value);
  return option?.label ?? activePeriod.value;
});

const infoBar = computed(() => hoveredBar.value ?? latestBar());

const infoItems = computed(() => {
  const bar = infoBar.value;
  if (!bar) return [];
  const items = [
    { label: "O", value: formatIndicatorValue(bar.open) },
    { label: "H", value: formatIndicatorValue(bar.high) },
    { label: "L", value: formatIndicatorValue(bar.low) },
    { label: "C", value: formatIndicatorValue(bar.close) },
  ];
  const volume = volumeValue(bar);
  if (volume !== null)
    items.push({ label: "VOL", value: formatIndicatorValue(volume) });
  if (isValidNumber(bar.fundingBps))
    items.push({
      label: "FUND",
      value: `${(bar.fundingBps / 100).toFixed(6)}%`,
    });
  const vwap = vwapValue(bar);
  if (vwap !== null)
    items.push({ label: "VWAP", value: formatIndicatorValue(vwap) });
  return items;
});

// --- 指标系列 ---
function ensureVolumeSeries(): ISeriesApi<"Histogram"> | null {
  if (!chart) return null;
  if (!volumeSeries) {
    volumeSeries = chart.addSeries(HistogramSeries, {
      color: "rgba(148, 163, 184, 0.45)",
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.78, bottom: 0 },
    });
  }
  return volumeSeries;
}

function ensureVwapSeries(): ISeriesApi<"Line"> | null {
  if (!chart) return null;
  if (!vwapSeries) {
    vwapSeries = chart.addSeries(LineSeries, {
      color: "#2563eb",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
  }
  return vwapSeries;
}

function updateIndicators(newData: CandlestickData[]): void {
  if (!chart) return;
  const volumeData: HistogramData[] = [];
  newData.forEach((bar) => {
    const value = volumeValue(bar);
    if (value === null) return;
    volumeData.push({
      time: bar.time as Time,
      value,
      color:
        bar.close >= bar.open
          ? "rgba(34, 197, 94, 0.38)"
          : "rgba(239, 68, 68, 0.38)",
    });
  });
  if (volumeData.length) {
    ensureVolumeSeries()?.setData(volumeData);
  } else if (volumeSeries) {
    chart.removeSeries(volumeSeries);
    volumeSeries = null;
  }

  const vwapData: LineData[] = [];
  newData.forEach((bar) => {
    const value = vwapValue(bar);
    if (value === null) return;
    vwapData.push({ time: bar.time as Time, value });
  });
  if (vwapData.length) {
    ensureVwapSeries()?.setData(vwapData);
  } else if (vwapSeries) {
    chart.removeSeries(vwapSeries);
    vwapSeries = null;
  }
}

function displayIndexForRawPos(pos: number): number | null {
  const bar = props.data[pos];
  if (!bar) return null;
  const seconds = timeToSeconds(bar.time);
  if (seconds === null) return null;
  return (
    displayIndexByTime.value.get(seconds) ??
    displayIndexByTime.value.get(bucketStart(seconds, activePeriod.value)) ??
    null
  );
}

function updateTradeMarkers(records: BacktestTradeRecord[]): void {
  if (!candlestickSeries) return;
  if (!tradeMarkers) {
    tradeMarkers = createSeriesMarkers(candlestickSeries, [], {
      zOrder: "top",
    });
  }
  const markers: SeriesMarker<Time>[] = [];
  records.forEach((record, recordIndex) => {
    record.trades?.forEach((trade, tradeIndex) => {
      const index = displayIndexForRawPos(trade.pos);
      if (index === null) return;
      const bar = displayData.value[index];
      if (!bar) return;
      const isTop = isTopTradeMarker(record.dir, trade.behavior);
      const price = isTop ? bar.high + 80 : bar.low - 80;
      markers.push({
        id: `${recordIndex}-${tradeIndex}-${trade.pos}`,
        time: bar.time as Time,
        position: isTop ? "atPriceTop" : "atPriceBottom",
        price,
        shape: isTop ? "arrowDown" : "arrowUp",
        color: "#f59e0b",
        text: markerText(
          recordIndex + 1,
          record.dir,
          trade.behavior,
          trade.lv,
          trade["position%"],
        ),
        size: 1.2,
      });
    });
  });
  tradeMarkers.setMarkers(markers);
}

function refreshChartData(newData: CandlestickData[]): void {
  if (!candlestickSeries) return;
  const priceScale = chart?.priceScale("right");
  // 模拟回测锁定价格轴: 先记住用户当前缩放, 数据更新后再原样恢复
  const lockedRange = props.autoPriceRange ? null : (priceScale?.getVisibleRange() ?? null);
  if (!props.autoPriceRange) priceScale?.applyOptions({ autoScale: false });
  candlestickSeries.setData(newData as LWCandlestickData[]);
  hoveredBar.value = newData.length
    ? (newData[newData.length - 1] ?? null)
    : null;
  if (props.autoPriceRange) setPriceVisibleRange(newData);
  updateIndicators(newData);
  updateTradeMarkers(props.tradeRecords);
  if (!props.autoPriceRange) {
    priceScale?.applyOptions({ autoScale: false });
    if (lockedRange) priceScale?.setVisibleRange(lockedRange);
  }
}

// 只水平滚动到最新一根；fitPrice 为 true 时按可见窗口重设一次价格范围
function scrollToLast(visibleBars = 80, fitPrice = false): void {
  if (!chart) return;
  const data = displayData.value;
  if (!data.length) return;
  const priceScale = chart.priceScale("right");
  // 先确保价格轴不自动缩放, 并在改时间轴前后恢复用户当前的纵向缩放
  const lockedRange = !props.autoPriceRange && !fitPrice
    ? (priceScale.getVisibleRange() ?? null)
    : null;
  if (!props.autoPriceRange) priceScale.applyOptions({ autoScale: false });
  const to = data.length - 1 + 8;
  const from = Math.max(to - visibleBars, 0);
  chart.timeScale().setVisibleLogicalRange({ from, to });
  if (!fitPrice) {
    if (lockedRange) priceScale.setVisibleRange(lockedRange);
    return;
  }
  const visible = data.slice(Math.max(data.length - visibleBars, 0));
  const prices = visible
    .flatMap((bar) => [bar.high, bar.low])
    .filter(isValidNumber);
  if (!prices.length) return;
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const padding = Math.max((max - min) * 0.12, Math.abs(max || min) * 0.001, 1);
  applyPriceRange({ from: min - padding, to: max + padding });
}

function setPriceVisibleRange(newData: CandlestickData[]): void {
  if (!chart) return;
  let min = Infinity;
  let max = -Infinity;
  for (const bar of newData) {
    if (isValidNumber(bar.low)) {
      min = Math.min(min, bar.low);
      max = Math.max(max, bar.low);
    }
    if (isValidNumber(bar.high)) {
      min = Math.min(min, bar.high);
      max = Math.max(max, bar.high);
    }
  }
  if (min === Infinity) return;
  const padding = Math.max((max - min) * 0.08, Math.abs(max || min) * 0.001, 1);
  applyPriceRange({ from: min - padding, to: max + padding });
}

function focusTrade(pos: number): void {
  const index = displayIndexForRawPos(pos);
  if (!chart || index === null) return;
  const sideBars = 35;
  const data = displayData.value;
  const from = Math.max(index - sideBars, 0);
  const to = Math.min(index + sideBars, data.length - 1);
  chart.timeScale().setVisibleLogicalRange({ from, to });
  const visibleBars = data.slice(from, to + 1);
  const prices = visibleBars
    .flatMap((bar) => [bar.high, bar.low])
    .filter(isValidNumber);
  if (!prices.length) return;
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const padding = Math.max((max - min) * 0.12, Math.abs(max || min) * 0.001, 1);
  applyPriceRange({ from: min - padding, to: max + padding });
}

// --- 绘图工具控制 ---
// 不在绘图模式下改 handleScroll/handleScale：DrawingManager 手势期间会自己 holdChart，
// 并在 pointerup 时还原按下瞬间的图表配置，两者互相覆盖会让滚轮/标尺缩放永久失效
function toggleTool(tool: DrawingKind): void {
  if (!drawingManager) return;
  drawingManager.setTool(activeTool.value === tool ? null : tool);
}

function drawingsStorageKey(): string {
  return `chart-drawings-${props.period ? periodLabel.value : "default"}`;
}

function saveDrawings(): void {
  if (!drawingManager) return;
  const key = drawingsStorageKey();
  try {
    localStorage.setItem(key, drawingManager.exportJSON());
  } catch {
    // 忽略存储配额等错误
  }
}

function restoreDrawings(): void {
  if (!drawingManager) return;
  const key = drawingsStorageKey();
  const saved = localStorage.getItem(key);
  if (saved) {
    try {
      drawingManager.importJSON(saved);
    } catch {
      // 数据损坏时忽略
    }
  }
}

function clearDrawings(): void {
  drawingManager?.clear();
  drawingManager?.setTool(null);
}

// --- 自定义拖拽平移（仅在非绘图模式下生效） ---
function handlePointerDown(event: PointerEvent): void {
  // 绘图模式下完全交由 DrawingManager 处理
  if (activeTool.value) return;

  if (
    !chart ||
    !chartContainer.value ||
    !candlestickSeries ||
    event.button !== 0
  )
    return;
  const rect = chartContainer.value.getBoundingClientRect();
  const localX = event.clientX - rect.left;
  const localY = event.clientY - rect.top;
  const priceScaleWidth = chart.priceScale("right").width();
  const timeScaleHeight = chart.timeScale().height();

  if (
    localX >= rect.width - priceScaleWidth ||
    localY >= rect.height - timeScaleHeight
  ) {
    dragState = null;
    return;
  }

  dragState = {
    pointerId: event.pointerId,
    startX: localX,
    startY: event.clientY,
    startLogicalRange: chart.timeScale().getVisibleLogicalRange(),
    startPriceRange: chart.priceScale("right").getVisibleRange(),
    priceHeight: Math.max(
      chartContainer.value.clientHeight - chart.timeScale().height(),
      1,
    ),
  };

  chartContainer.value.setPointerCapture(event.pointerId);
  event.preventDefault();
}

function handlePointerMove(event: PointerEvent): void {
  if (!chart || !chartContainer.value) return;
  if (!dragState || dragState.pointerId !== event.pointerId) return;
  const rect = chartContainer.value.getBoundingClientRect();
  const currentX = event.clientX - rect.left;

  const logicalRange = dragState.startLogicalRange;
  if (logicalRange) {
    const fromX = chart.timeScale().coordinateToLogical(dragState.startX);
    const toX = chart.timeScale().coordinateToLogical(currentX);
    if (fromX !== null && toX !== null) {
      const delta = fromX - toX;
      chart.timeScale().setVisibleLogicalRange({
        from: logicalRange.from + delta,
        to: logicalRange.to + delta,
      });
    }
  }

  const priceRange = dragState.startPriceRange;
  if (priceRange) {
    const size = priceRange.to - priceRange.from;
    const delta =
      ((event.clientY - dragState.startY) / dragState.priceHeight) * size;
    applyPriceRange({
      from: priceRange.from + delta,
      to: priceRange.to + delta,
    });
  }

  event.preventDefault();
}

function handlePointerUp(event: PointerEvent): void {
  if (!chartContainer.value) return;
  schedulePriceClamp();
  if (!dragState || dragState.pointerId !== event.pointerId) return;
  chartContainer.value.releasePointerCapture(event.pointerId);
  dragState = null;
}

// --- 初始化图表 ---
function initChart(): void {
  if (!chartContainer.value) return;

  chart = createChart(chartContainer.value, {
    autoSize: props.autosize,
    width: chartContainer.value.clientWidth,
    height: props.fill ? chartContainer.value.clientHeight : props.height,
    layout: {
      background: { color: "#fbf7ec" },
      textColor: "#74664f",
      attributionLogo: false,
    },
    grid: {
      vertLines: { color: "#eadfc8" },
      horzLines: { color: "#eadfc8" },
    },
    handleScroll: {
      mouseWheel: true,
      pressedMouseMove: false,
      horzTouchDrag: true,
      vertTouchDrag: true,
    },
    handleScale: {
      mouseWheel: true,
      pinch: true,
      axisPressedMouseMove: { time: true, price: true },
      axisDoubleClickReset: { time: true, price: true },
    },
    crosshair: { mode: CrosshairMode.Normal },
    rightPriceScale: {
      borderColor: "#ddd0b2",
      autoScale: false,
    },
    timeScale: {
      borderColor: "#ddd0b2",
      timeVisible: true,
      secondsVisible: false,
      rightOffset: 8,
      shiftVisibleRangeOnNewBar: true,
    },
  });

  candlestickSeries = chart.addSeries(CandlestickSeries, {
    upColor: "#22c55e",
    downColor: "#ef4444",
    borderUpColor: "#22c55e",
    borderDownColor: "#ef4444",
    wickUpColor: "#22c55e",
    wickDownColor: "#ef4444",
  });

  chart.priceScale("right").applyOptions({
    autoScale: false,
    scaleMargins: { top: 0.1, bottom: 0.25 },
  });

  // --- 初始化绘图管理器 ---
  if (candlestickSeries) {
    drawingManager = new DrawingManager(chart, candlestickSeries, {
      magnet: "weak", // 弱吸附，贴合K线高低点
      bars: drawingBars, // 成交量分布图需要带 volume 的K线
    });
    // 放置完成后库会自动 setTool(null)，同步按钮高亮与拖拽放行状态
    drawingManager.on("tool", (tool) => {
      activeTool.value = tool;
    });
  }

  if (displayData.value.length > 0 && candlestickSeries) {
    refreshChartData(displayData.value);
  }

  // 恢复已保存的绘图（需在数据设置之后）
  restoreDrawings();

  chart.subscribeCrosshairMove((param) => {
    if (!param.time || !param.point || !candlestickSeries) {
      hoveredBar.value = latestBar();
      emit("crosshairMove", null);
      return;
    }
    hoveredBar.value = resolveBarByTime(param.time);
    const price = candlestickSeries.coordinateToPrice(param.point.y) ?? 0;
    emit("crosshairMove", { time: param.time, price });
  });

  chart.subscribeClick((param) => {
    if (!param.time || !param.point || !candlestickSeries) return;
    const price = candlestickSeries.coordinateToPrice(param.point.y) ?? 0;
    emit("click", { time: param.time, price });
  });
}

function handleResize(): void {
  if (!chart || !chartContainer.value) return;
  if (!chart.autoSizeActive()) {
    const height = props.fill
      ? chartContainer.value.clientHeight
      : props.height;
    chart.resize(chartContainer.value.clientWidth, height, true);
  }
}

function updateData(newData: CandlestickData[]): void {
  refreshChartData(newData);
}

function appendData(bar: CandlestickData): void {
  if (candlestickSeries) {
    candlestickSeries.update(bar as LWCandlestickData);
    const volume = volumeValue(bar);
    if (volume !== null) {
      ensureVolumeSeries()?.update({
        time: bar.time as Time,
        value: volume,
        color:
          bar.close >= bar.open
            ? "rgba(34, 197, 94, 0.38)"
            : "rgba(239, 68, 68, 0.38)",
      });
    }
    const vwap = vwapValue(bar);
    if (vwap !== null) {
      ensureVwapSeries()?.update({ time: bar.time as Time, value: vwap });
    }
  }
}

function handlePeriodChange(event: Event): void {
  const value = (event.target as HTMLSelectElement).value as KlinePeriod;
  innerPeriod.value = value;
  emit("update:period", value);
}

watch(displayData, (newData) => {
  updateData(newData);
});

watch(
  () => props.tradeRecords,
  (records) => {
    updateTradeMarkers(records);
  },
);

onMounted(() => {
  initChart();
  chartContainer.value?.addEventListener("pointerdown", handlePointerDown);
  chartContainer.value?.addEventListener("pointermove", handlePointerMove);
  chartContainer.value?.addEventListener("pointerup", handlePointerUp);
  chartContainer.value?.addEventListener("pointercancel", handlePointerUp);
  chartContainer.value?.addEventListener("wheel", schedulePriceClamp, {
    passive: true,
  });
  window.addEventListener("pointerup", schedulePriceClamp, true);
  window.addEventListener("pointercancel", schedulePriceClamp, true);
  if (props.autosize) {
    window.addEventListener("resize", handleResize);
  }
});

onUnmounted(() => {
  saveDrawings(); // 组件卸载前自动保存
  chartContainer.value?.removeEventListener("pointerdown", handlePointerDown);
  chartContainer.value?.removeEventListener("pointermove", handlePointerMove);
  chartContainer.value?.removeEventListener("pointerup", handlePointerUp);
  chartContainer.value?.removeEventListener("pointercancel", handlePointerUp);
  chartContainer.value?.removeEventListener("wheel", schedulePriceClamp);
  window.removeEventListener("pointerup", schedulePriceClamp, true);
  window.removeEventListener("pointercancel", schedulePriceClamp, true);
  if (priceClampFrame) {
    cancelAnimationFrame(priceClampFrame);
    priceClampFrame = 0;
  }
  window.clearTimeout(priceClampTimer);
  if (props.autosize) {
    window.removeEventListener("resize", handleResize);
  }
  drawingManager?.destroy(); // 解绑管理器的 window 键盘监听与 series primitive
  drawingManager = null;
  if (chart) {
    chart.remove();
    chart = null;
  }
});

defineExpose({
  updateData,
  appendData,
  focusTrade,
  scrollToLast,
  clearDrawings,
  saveDrawings,
});
</script>

<template>
  <div class="flex flex-col w-full" :style="fill ? { height: '100%' } : {}">
    <!-- 绘图工具栏 -->
    <div
      class="flex items-center gap-1 px-2 py-1 bg-paper-soft border-b border-paper-line"
    >
      <button
        v-for="tool in drawingTools"
        :key="tool.kind"
        class="flex items-center justify-center w-7 h-7 text-xs font-semibold rounded transition-colors"
        :class="
          activeTool === tool.kind
            ? 'bg-ink text-paper'
            : 'text-ink-soft hover:bg-paper-line/50'
        "
        :title="tool.title"
        @click="toggleTool(tool.kind)"
      >
        {{ tool.label }}
      </button>
      <div class="w-px h-4 mx-1 bg-paper-line" />
      <button
        class="px-2 h-7 text-xs font-semibold rounded text-ink-faint hover:bg-paper-line/50 transition-colors"
        title="清除所有绘图"
        @click="clearDrawings"
      >
        清除
      </button>
      <div class="w-px h-4 mx-1 bg-paper-line" />
      <select
        :value="activePeriod"
        title="选择周期"
        class="h-7 cursor-pointer rounded border border-paper-line bg-paper px-2 text-xs font-semibold text-ink-soft focus:outline-none focus:ring-1 focus:ring-indigo-400/40"
        @change="handlePeriodChange"
      >
        <option
          v-for="item in periodOptions"
          :key="item.value"
          :value="item.value"
        >
          {{ item.label }}
        </option>
      </select>
    </div>

    <!-- 图表容器 -->
    <div
      ref="chartContainer"
      class="relative w-full select-none overflow-hidden"
      :style="
        fill
          ? { height: '100%', minHeight: '240px', touchAction: 'none' }
          : { height: `${height}px`, touchAction: 'none' }
      "
    >
      <div
        v-if="displayData.length"
        class="pointer-events-none absolute left-2 top-2 z-10 flex flex-wrap items-center gap-x-3 gap-y-1 rounded border border-paper-line/80 bg-paper/90 px-2 py-1 text-xs font-semibold text-ink-soft backdrop-blur-sm"
      >
        <span class="text-ink">{{ periodLabel }}</span>
        <span
          v-for="item in infoItems"
          :key="item.label"
          class="whitespace-nowrap"
        >
          <span class="text-ink-faint">{{ item.label }}</span>
          <span class="ml-1 text-ink">{{ item.value }}</span>
        </span>
      </div>
      <div
        v-else
        class="absolute inset-0 z-10 flex items-center justify-center bg-paper-soft"
      >
        <div class="flex flex-col items-center gap-2 text-ink-faint">
          <i class="ri-line-chart-line text-2xl"></i>
          <span class="text-xs">暂无 K 线数据</span>
        </div>
      </div>
    </div>
  </div>
</template>
