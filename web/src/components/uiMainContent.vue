<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import type { MenuItem } from '../types'

// 页面映射
const PageMarket = defineAsyncComponent(() => import('./pages/PageMarket.vue'))
const PageStrategy = defineAsyncComponent(() => import('./pages/PageStrategy.vue'))
const PageBacktest = defineAsyncComponent(() => import('./pages/PageBacktest.vue'))
const PageOrders = defineAsyncComponent(() => import('./pages/PageOrders.vue'))
const PageSettings = defineAsyncComponent(() => import('./pages/PageSettings.vue'))
const pageComponents: Record<number, ReturnType<typeof defineAsyncComponent>> = {
  1: PageMarket,
  2: PageStrategy,
  3: PageBacktest,
  4: PageOrders,
  5: PageSettings
}

// 当前页面组件
const props = defineProps<{activeItem: MenuItem}>()
const currentPage = computed(() => pageComponents[props.activeItem.id])

</script>

<template>
  <main class="flex-1 flex flex-col min-w-0 overflow-hidden relative bg-gray-100">
    <!-- 顶部标题 -->
    <header class="h-16 bg-white border-b border-gray-200 flex items-center justify-center px-8 shadow-sm shrink-0">
      <h2 class="text-xl font-bold text-gray-800">{{ activeItem.name }}</h2>
    </header>

    <!-- 内容区域 -->
    <div class="flex-1 overflow-hidden">
      <Suspense>
        <template #default>
          <KeepAlive>
            <component :is="currentPage" :key="activeItem.id" />
          </KeepAlive>
        </template>
        <template #fallback>
          <div class="h-full flex items-center justify-center">
            <div class="text-gray-500">加载中...</div>
          </div>
        </template>
      </Suspense>
    </div>
  </main>
</template>
