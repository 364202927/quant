<script setup lang="ts">
import {
  computed,
  onActivated,
  onMounted,
  onUnmounted,
  ref,
  shallowRef,
} from "vue";
import * as echarts from "echarts";
import LightweightChart from "../../utils/LightweightChart.vue";
import { eMsg, type CandlestickData } from "../../types";
import { postMessage } from "../../utils/common";
import { filterByRange, resampleKline, type KlinePeriod } from "../../utils/kline";

const coins = ref<string[]>([]);
const selectedCoin = ref("");
const startDate = ref("");
const endDate = ref("");
const period = ref<KlinePeriod>("5m");
const allKline = shallowRef<CandlestickData[]>([]);
const periodKline = computed(() => resampleKline(allKline.value, period.value));
const klineData = computed<CandlestickData[]>(() =>
  filterByRange(
    periodKline.value,
    startDate.value,
    endDate.value,
    period.value,
  ),
);
const isLoading = ref(false);
const loadError = ref("");
const marketTitle = computed(() => selectedCoin.value || "K线");
const periodLabel = computed(() =>
  period.value === "1M" ? "month" : period.value,
);
const dateLabel = computed(() => {
  if (startDate.value && endDate.value)
    return `${startDate.value} ~ ${endDate.value}`;
  if (startDate.value) return `${startDate.value} 起`;
  if (endDate.value) return `至 ${endDate.value}`;
  return "全部历史";
});
const klineSummary = computed(() => {
  if (!selectedCoin.value) return "请选择币种和日期";
  return `${dateLabel.value} · ${periodLabel.value} · ${klineData.value.length} 根`;
});

const fearGreedValue = ref(50);
const fearGreedChart = ref<HTMLDivElement | null>(null);
let echartsInstance: echarts.ECharts | null = null;
let loadToken = 0;
let cachedCoin = "";
let cachedKline: CandlestickData[] = [];

function toNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function normalizeKlineRows(rows: unknown): CandlestickData[] {
  if (!Array.isArray(rows)) return [];

  const result: CandlestickData[] = [];
  rows.forEach((row) => {
    const item = row as Record<string, unknown>;
    const open = toNumber(item.open);
    const high = toNumber(item.high);
    const low = toNumber(item.low);
    const close = toNumber(item.close);
    if (
      item.time === undefined ||
      open === null ||
      high === null ||
      low === null ||
      close === null
    )
      return;

    const bar: CandlestickData = {
      time: typeof item.time === "number" ? item.time : String(item.time),
      open,
      high,
      low,
      close,
    };
    const volume = toNumber(item.volume ?? item.vol);
    if (volume !== null) bar.volume = volume;
    const fundingBps = toNumber(item.funding_bps ?? item.fundingBps);
    if (fundingBps !== null) bar.fundingBps = fundingBps;
    result.push(bar);
  });
  return result;
}

async function loadCoins(): Promise<void> {
  isLoading.value = true;
  loadError.value = "";
  try {
    const response = await postMessage(eMsg.ePage_k);
    const list = response.received?.args;
    coins.value = Array.isArray(list)
      ? list.filter((item): item is string => typeof item === "string")
      : [];
  } catch (error) {
    console.error("币种列表加载失败", error);
    loadError.value = "币种列表加载失败";
    coins.value = [];
  } finally {
    isLoading.value = false;
  }
}

async function loadKline(): Promise<void> {
  const token = ++loadToken;
  const coin = selectedCoin.value;
  allKline.value = [];
  loadError.value = "";
  if (!coin) {
    isLoading.value = false;
    return;
  }

  if (coin === cachedCoin && cachedKline.length) {
    allKline.value = cachedKline;
    isLoading.value = false;
    return;
  }
  if (coin !== cachedCoin) {
    cachedCoin = "";
    cachedKline = [];
  }

  isLoading.value = true;
  try {
    const response = await postMessage(eMsg.ePage_k, coin);
    if (token !== loadToken) return;
    const rows = normalizeKlineRows(response.received?.args);
    cachedCoin = coin;
    cachedKline = rows;
    allKline.value = rows;
  } catch (error) {
    if (token !== loadToken) return;
    console.error("K线加载失败", error);
    loadError.value = "K线加载失败";
    allKline.value = [];
  } finally {
    if (token === loadToken) isLoading.value = false;
  }
}

function resetMarket(): void {
  loadToken += 1;
  coins.value = [];
  selectedCoin.value = "";
  startDate.value = "";
  endDate.value = "";
  period.value = "5m";
  allKline.value = [];
  isLoading.value = false;
  loadError.value = "";
  void loadCoins();
}

// 获取恐慌贪婪指数颜色
function getFearGreedColor(value: number): string {
  if (value < 25) return "#ef4444";
  if (value < 50) return "#f97316";
  if (value < 75) return "#eab308";
  return "#22c55e";
}

// 获取恐慌贪婪文字档位
function getFearGreedLabel(value: number): string {
  if (value < 25) return "极度恐惧";
  if (value < 50) return "恐惧";
  if (value < 75) return "中性";
  return "极度贪婪";
}

// 初始化恐慌贪婪指数图表
function initFearGreedChart(): void {
  if (!fearGreedChart.value) return;

  echartsInstance = echarts.init(fearGreedChart.value);

  const option: echarts.EChartsOption = {
    series: [
      {
        type: "gauge",
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 100,
        splitNumber: 10,
        itemStyle: {
          color: getFearGreedColor(fearGreedValue.value),
        },
        progress: { show: true, width: 20 },
        pointer: { show: false },
        axisLine: {
          lineStyle: {
            width: 20,
            color: [
              [0.25, "#ef4444"],
              [0.5, "#f97316"],
              [0.75, "#eab308"],
              [1, "#22c55e"],
            ],
          },
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        title: {
          offsetCenter: [0, "32%"],
          fontSize: 11,
          color: "#9c8d74",
          fontWeight: "normal",
        },
        detail: {
          valueAnimation: true,
          fontSize: 40,
          fontWeight: "bold",
          offsetCenter: [0, "0%"],
          formatter: "{value}",
          color: "#3a3226",
        },
        data: [{ value: fearGreedValue.value, name: "当前指数" }],
      },
    ],
  };

  echartsInstance.setOption(option);
}

function handleResize(): void {
  echartsInstance?.resize();
}

onActivated(resetMarket);

onMounted(() => {
  fearGreedValue.value = Math.floor(Math.random() * 100);
  initFearGreedChart();
  window.addEventListener("resize", handleResize);
});

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
  echartsInstance?.dispose();
  echartsInstance = null;
});
</script>

<template>
  <div class="page-body flex flex-col">
    <div class="grid min-h-0 flex-1 gap-4 xl:grid-cols-3">
      <!-- K线图区域 -->
      <section class="panel flex min-h-[460px] flex-col p-4 xl:col-span-2">
        <header class="mb-3 flex shrink-0 flex-col gap-2">
          <div class="flex items-start justify-between gap-3">
            <div>
              <h2 class="text-base font-semibold text-ink">
                {{ marketTitle }}
              </h2>
              <p class="mt-0.5 text-xs text-ink-soft">{{ klineSummary }}</p>
            </div>
            <span
              v-if="isLoading"
              class="inline-flex items-center gap-1.5 rounded-full border border-paper-line bg-paper px-2.5 py-1 text-[11px] text-ink-soft"
            >
              <i class="ri-loader-4-line animate-spin text-xs"></i>
              加载中…
            </span>
            <span
              v-else-if="loadError"
              class="rounded-full border border-rose-200 bg-rose-50 px-2.5 py-1 text-[11px] text-rose-600"
            >
              {{ loadError }}
            </span>
            <span
              v-else
              class="rounded-full border border-paper-line bg-paper px-2.5 py-1 text-[11px] text-ink-soft"
            >
              本地历史
            </span>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <div class="relative min-w-40 max-w-64 flex-1">
              <select
                v-model="selectedCoin"
                @change="loadKline()"
                :disabled="isLoading && !coins.length"
                title="选择币种"
                class="w-full cursor-pointer appearance-none rounded-lg border border-paper-line bg-paper py-1.5 pl-3 pr-8 text-sm font-medium text-ink transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-indigo-400/40 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <option value="" disabled>
                  {{ coins.length ? "选择币种" : "暂无币种" }}
                </option>
                <option v-for="coin in coins" :key="coin" :value="coin">
                  {{ coin }}
                </option>
              </select>
              <svg
                class="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                stroke-width="2.5"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </div>
            <input
              v-model="startDate"
              type="date"
              :disabled="!selectedCoin"
              :max="endDate || undefined"
              title="开始日期"
              class="rounded-lg border border-paper-line bg-paper px-3 py-1.5 text-sm text-ink transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-indigo-400/40 disabled:cursor-not-allowed disabled:opacity-60"
            />
            <span class="text-sm text-ink-faint">~</span>
            <input
              v-model="endDate"
              type="date"
              :disabled="!selectedCoin"
              :min="startDate || undefined"
              title="结束日期"
              class="rounded-lg border border-paper-line bg-paper px-3 py-1.5 text-sm text-ink transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-indigo-400/40 disabled:cursor-not-allowed disabled:opacity-60"
            />
          </div>
        </header>
        <LightweightChart
          v-model:period="period"
          class="min-h-0 flex-1"
          :data="klineData"
          fill
        />
      </section>

      <!-- 恐慌贪婪指数 -->
      <section class="panel flex min-h-[460px] flex-col p-4">
        <header class="flex shrink-0 items-start justify-between gap-3">
          <div>
            <h2 class="text-base font-semibold text-ink">市场情绪</h2>
            <p class="mt-0.5 text-xs text-ink-soft">恐慌与贪婪指数</p>
          </div>
          <span
            class="rounded-full border px-2.5 py-1 text-[11px] font-medium"
            :style="{
              color: getFearGreedColor(fearGreedValue),
              borderColor: getFearGreedColor(fearGreedValue) + '55',
            }"
          >
            {{ getFearGreedLabel(fearGreedValue) }}
          </span>
        </header>

        <div
          class="flex flex-1 flex-col items-center justify-center gap-3 py-3"
        >
          <div ref="fearGreedChart" class="h-56 w-full max-w-sm"></div>
          <div
            class="grid w-full max-w-sm grid-cols-3 gap-2 border-t border-paper-line pt-4 text-center"
          >
            <div>
              <span
                class="mx-auto mb-1 block h-1.5 w-1.5 rounded-full bg-red-500"
              ></span>
              <p class="text-[11px] font-medium text-ink-soft">0–24</p>
              <p class="text-[10px] text-ink-faint">恐惧</p>
            </div>
            <div>
              <span
                class="mx-auto mb-1 block h-1.5 w-1.5 rounded-full bg-amber-500"
              ></span>
              <p class="text-[11px] font-medium text-ink-soft">25–74</p>
              <p class="text-[10px] text-ink-faint">中性</p>
            </div>
            <div>
              <span
                class="mx-auto mb-1 block h-1.5 w-1.5 rounded-full bg-emerald-500"
              ></span>
              <p class="text-[11px] font-medium text-ink-soft">75–100</p>
              <p class="text-[10px] text-ink-faint">贪婪</p>
            </div>
          </div>
          <p
            class="max-w-sm text-center text-[11px] leading-relaxed text-ink-faint"
          >
            指数越低代表市场越恐慌，越高代表越贪婪，可作为仓位与情绪的辅助参考。
          </p>
        </div>
      </section>
    </div>
  </div>
</template>
