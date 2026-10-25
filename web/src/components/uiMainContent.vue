<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'UiMainContent'
})
</script>

<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { type MenuItem, eMenuId } from '../types'
import uiLog from './uiLog.vue'

// 页面映射
const PageMarket = defineAsyncComponent(() => import('./pages/PageMarket.vue'))
const PageStrategy = defineAsyncComponent(() => import('./pages/PageStrategy.vue'))
const PageBacktest = defineAsyncComponent(() => import('./pages/PageBacktest.vue'))
const PageOrders = defineAsyncComponent(() => import('./pages/PageOrders.vue'))
const PageAssets = defineAsyncComponent(() => import('./pages/PageAssets.vue'))
const PageSettings = defineAsyncComponent(() => import('./pages/PageSettings.vue'))
const pageComponents: Record<eMenuId, ReturnType<typeof defineAsyncComponent>> = {
  [eMenuId.eAssets]: PageAssets,
  [eMenuId.eMarket]: PageMarket,
  [eMenuId.eStrategy]: PageStrategy,
  [eMenuId.eBacktest]: PageBacktest,
  [eMenuId.eOrders]: PageOrders,
  [eMenuId.eSettings]: PageSettings
}

const pageHints: Record<eMenuId, string> = {
  [eMenuId.eAssets]: '账户资产与交易所分布',
  [eMenuId.eMarket]: '行情走势与市场情绪',
  [eMenuId.eStrategy]: '策略实例与运行状态',
  [eMenuId.eBacktest]: 'K 线回放与绩效评估',
  [eMenuId.eOrders]: '订单筛选与成交跟踪',
  [eMenuId.eSettings]: '交易接口与通知配置'
}

// 当前页面组件
const props = defineProps<{ activeItem: MenuItem }>()
const currentPage = computed(() => pageComponents[props.activeItem.id])
const currentHint = computed(() => pageHints[props.activeItem.id])

// 日志面板：宽屏默认展开；设置页及窄屏默认收起
const wideScreen = window.matchMedia('(min-width: 1280px)')
const logOpen = ref(false)
watch(() => props.activeItem.id, (id) => {
  logOpen.value = id !== eMenuId.eSettings && wideScreen.matches
}, { immediate: true })

function toggleLog(): void {
  logOpen.value = !logOpen.value
}
</script>

<template>
  <main class="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-paper">
    <!-- 顶栏：页面定位 + 全局日志开关 -->
    <header class="flex h-14 shrink-0 items-center gap-3 border-b border-paper-line bg-paper/85 px-4 backdrop-blur md:px-5">
      <div class="flex min-w-0 items-center gap-3">
        <span class="hidden h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-paper-line bg-paper-soft text-ink-soft sm:flex">
          <i :class="[activeItem.icon, 'text-base']"></i>
        </span>
        <div class="min-w-0">
          <h1 class="truncate text-base font-semibold leading-tight text-ink">{{ activeItem.name }}</h1>
          <p class="hidden truncate text-[11px] leading-tight text-ink-soft sm:block">{{ currentHint }}</p>
        </div>
      </div>

      <div class="ml-auto flex items-center gap-2">
        <span class="hidden items-center gap-1.5 rounded-full border border-paper-line bg-paper-soft px-2.5 py-1 text-[11px] text-ink-soft md:inline-flex">
          <i class="ri-hard-drive-3-line text-xs"></i>
          本地工作台
        </span>
        <button @click="toggleLog" :title="logOpen ? '收起运行日志' : '展开运行日志'"
          class="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors"
          :class="logOpen
            ? 'border-paper-line bg-paper-soft text-ink'
            : 'border-transparent text-ink-soft hover:border-paper-line hover:bg-paper-soft hover:text-ink'">
          <i class="ri-terminal-box-line text-base"></i>
          <span class="hidden sm:inline">{{ logOpen ? '收起日志' : '运行日志' }}</span>
        </button>
      </div>
    </header>

    <!-- 内容区域 -->
    <div class="relative flex min-h-0 flex-1 overflow-hidden">
      <div class="min-w-0 flex-1 overflow-hidden">
        <Suspense>
          <template #default>
            <KeepAlive>
              <component :is="currentPage" :key="activeItem.id" />
            </KeepAlive>
          </template>
          <template #fallback>
            <div class="flex h-full items-center justify-center">
              <div class="flex items-center gap-2 text-sm text-ink-soft">
                <i class="ri-loader-4-line animate-spin"></i>
                加载中…
              </div>
            </div>
          </template>
        </Suspense>
      </div>
      <Transition name="log-slide">
        <uiLog v-if="logOpen" @close="logOpen = false" />
      </Transition>
    </div>
  </main>
</template>
