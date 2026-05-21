<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'UiSidebar'
})
</script>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { type MenuItem, eMenuId } from '../types'

// 定义菜单数据
const menuItems: MenuItem[] = [
  { id: eMenuId.eSettings, name: '设  置', icon: 'ri-settings-3-line' },
  { id: eMenuId.eAssets, name: '资  产', icon: 'ri-wallet-3-line' },
  { id: eMenuId.eMarket, name: '行  情', icon: 'ri-dashboard-line' },
  { id: eMenuId.eStrategy, name: '策略管理', icon: 'ri-user-settings-line' },
  { id: eMenuId.eBacktest, name: '回  测', icon: 'ri-file-list-3-line' },
  { id: eMenuId.eOrders, name: '订单管理', icon: 'ri-pie-chart-2-line' },
]

const emit = defineEmits<{
  'select-item': [item: MenuItem]
}>()

// 用户名
const userName = ref<string>('')

// 按钮是否禁用
const isDisabled = ref<boolean>(false)

// 当前激活项
const activeItem = ref<MenuItem>(menuItems[4]!)

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
  // setItem(5) // 默认选中设置
})

// export
defineExpose({
  init,
  setLock,
  setItem
})
</script>

<template>
  <aside class="w-52 bg-gray-900 text-white flex flex-col shadow-2xl z-10 shrink-0">
    <!-- Logo 区域 -->
    <div class="h-16 flex items-center px-6 border-b border-gray-800 justify-center">
      <span class="text-lg font-bold tracking-wide ">Dashboard</span>
    </div>

    <!-- 菜单列表 -->
    <nav class="flex-1 overflow-y-auto py-4">
      <ul class="space-y-1">
        <li v-for="item in menuItems.filter(i => i.id !== eMenuId.eSettings)" :key="item.id">
          <button @click="onSelect(item)" :disabled="isDisabled || activeItem.id === item.id"
            class="w-full box-border flex items-center justify-center px-6 py-3 text-lg transition-all duration-200 border-l-4"
            :class="[
              activeItem.id === item.id
                ? 'bg-transparent border-indigo-500 text-blue-400 hover:text-blue-500 font-medium'
                : 'bg-transparent text-white hover:text-white',
              (isDisabled || activeItem.id === item.id) ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
            ]">
            <i :class="[item.icon, 'mr-3 text-2xl']"></i>
            <span>{{ item.name }}</span>
          </button>
        </li>
      </ul>
    </nav>

    <!-- 底部用户信息 -->
    <div class="p-4 border-t border-gray-800">
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-3 flex-1 min-w-0">
          <div class="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center text-white font-bold text-sm">
            {{ getUserInitial() }}
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-small truncate">{{ userName }}</p>
          </div>
        </div>
        <!-- 设置按钮 -->
        <button @click="onSettingsClick"
          class="w-13 h-13 flex items-center justify-center overflow-visible opacity-70 hover:opacity-100 transition-opacity cursor-pointer flex-shrink-0"
          :class="[activeItem.id === eMenuId.eSettings ? 'opacity-100' : '']">
          <img src="/setting.png" alt="设置" class="w-10 h-10 object-cover" />
        </button>
      </div>
    </div>
  </aside>
</template>
