<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'UiSidebar'
})
</script>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { type MenuItem, eMenuId } from '../types'

// 菜单按交易流程排序：看行情 → 管策略 → 做回测 → 跟订单 → 看资产
const menuItems: MenuItem[] = [
  { id: eMenuId.eMarket, name: '行情', icon: 'ri-line-chart-line' },
  { id: eMenuId.eStrategy, name: '策略管理', icon: 'ri-node-tree' },
  { id: eMenuId.eBacktest, name: '回测', icon: 'ri-history-line' },
  { id: eMenuId.eOrders, name: '订单管理', icon: 'ri-list-check-2' },
  { id: eMenuId.eAssets, name: '资产', icon: 'ri-wallet-3-line' },
  { id: eMenuId.eSettings, name: '设置', icon: 'ri-settings-3-line' },
]

const emit = defineEmits<{
  'select-item': [item: MenuItem]
}>()

// 用户名
const userName = ref<string>('')

// 按钮是否禁用
const isDisabled = ref<boolean>(false)

// 当前激活项
const activeItem = ref<MenuItem>(menuItems[0]!)

// 初始化函数
const init = (strName: string) => {
  userName.value = strName
  isDisabled.value = false // 初始化完成后启用按钮
}

// 选择菜单项
const onSelect = (item: MenuItem) => {
  if (isDisabled.value || activeItem.value.id === item.id) return
  activeItem.value = item
  emit('select-item', item)
}

// 设置按钮点击（不受禁用限制）
const onSettingsClick = () => {
  const settingsItem = menuItems.find(i => i.id === eMenuId.eSettings)!
  activeItem.value = settingsItem
  emit('select-item', settingsItem)
}

// 获取用户名首字母
const getUserInitial = () => {
  return userName.value ? userName.value.charAt(0).toUpperCase() : '?'
}

// 设置菜单锁定状态
const setLock = (locked: boolean) => {
  isDisabled.value = locked
}

const setItem = (id: eMenuId) => {
  const item = menuItems.find(i => i.id === id)
  if (item) {
    activeItem.value = item
    emit('select-item', item)
  }
}

// 初始化
onMounted(() => {
  console.log('侧边栏组件挂载完成')
  setLock(true)  // 初始状态锁定
})

// export
defineExpose({
  init,
  setLock,
  setItem
})
</script>

<template>
  <aside class="flex w-16 shrink-0 flex-col border-r border-black/20 bg-[#2a241c] text-[#e9dfcc] shadow-2xl z-10 md:w-56">
    <!-- Logo 区域 -->
    <div class="flex h-16 shrink-0 items-center justify-center gap-3 border-b border-white/10 px-3 md:justify-start md:px-5">
      <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#d3ab67] text-[#2a241c]">
        <i class="ri-pulse-line text-lg"></i>
      </div>
      <div class="hidden min-w-0 md:block">
        <p class="truncate text-sm font-semibold tracking-wide text-[#f4e9d3]">Quant Desk</p>
        <p class="truncate text-[10px] uppercase tracking-[0.18em] text-[#8f816b]">Trading Terminal</p>
      </div>
    </div>

    <!-- 菜单列表 -->
    <nav class="flex-1 overflow-y-auto px-2 py-4 md:px-3">
      <p class="mb-2 hidden px-2 text-[10px] font-medium uppercase tracking-[0.2em] text-[#7d705d] md:block">工作台</p>
      <ul class="space-y-1">
        <li v-for="item in menuItems.filter(i => i.id !== eMenuId.eSettings)" :key="item.id">
          <button @click="onSelect(item)" :disabled="isDisabled || activeItem.id === item.id" :title="item.name"
            class="relative flex w-full items-center justify-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors duration-150 md:justify-start"
            :class="[
              activeItem.id === item.id
                ? 'bg-white/[0.07] text-[#f0d6a2]'
                : 'text-[#b6a98f] hover:bg-white/5 hover:text-[#f5ead6]',
              isDisabled ? 'cursor-not-allowed opacity-45' : 'cursor-pointer'
            ]">
            <span v-if="activeItem.id === item.id"
              class="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r bg-[#d3ab67]"></span>
            <i :class="[item.icon, 'shrink-0 text-xl']"></i>
            <span class="hidden truncate md:inline">{{ item.name }}</span>
          </button>
        </li>
      </ul>
    </nav>

    <!-- 底部用户信息 -->
    <div class="border-t border-white/10 p-3 md:p-4">
      <div class="flex items-center justify-center gap-3 md:justify-between">
        <div class="flex min-w-0 items-center gap-3">
          <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#d3ab67] text-sm font-bold text-[#2a241c]">
            {{ getUserInitial() }}
          </div>
          <div class="hidden min-w-0 md:block">
            <p class="text-[10px] uppercase tracking-wider text-[#7d705d]">当前用户</p>
            <p class="truncate text-sm text-[#e9dfcc]">{{ userName || '未登录' }}</p>
          </div>
        </div>
        <!-- 设置按钮 -->
        <button @click="onSettingsClick" title="设置"
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors"
          :class="activeItem.id === eMenuId.eSettings
            ? 'bg-white/[0.07] text-[#f0d6a2]'
            : 'text-[#8f816b] hover:bg-white/5 hover:text-[#f5ead6]'">
          <i class="ri-settings-3-line text-xl"></i>
        </button>
      </div>
    </div>
  </aside>
</template>
