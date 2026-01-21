<script setup lang="ts">
import { ref, inject,onActivated } from 'vue'
import NotificationItem from '../../utils/NotificationItem.vue'
import ExchangeItem from '../../utils/ExchangeItem.vue'
import type { NotificationConfig, ExchangeConfig } from '../../types'
import type { userDataStore } from '../../types/userDataStore'

// 定义事件
const emit = defineEmits<{
  save: [data: {
    accountName: string
    notifications: NotificationConfig[]
    exchanges: ExchangeConfig[]
  }]
  activate: []
}>()

type SettingSection = 'account' | 'notification' | 'exchange'

const SECTION_BUTTONS: { key: SettingSection; label: string }[] = [
  { key: 'account', label: '账号信息' },
  { key: 'notification', label: '通知设置' },
  { key: 'exchange', label: '交易所API' }
]

const activeSection = ref<SettingSection>('account')
const accountName = ref('')
const notifications = ref<NotificationConfig[]>([])
const exchanges = ref<ExchangeConfig[]>([])

function addNotification(): void {
  notifications.value.push({
    id: String(Date.now()),
    enable: true,
    token: '',
    chatId: ''
  })
}

function removeNotification(id: string): void {
  const index = notifications.value.findIndex(n => n.id === id)
  if (index > -1) notifications.value.splice(index, 1)
}

function updateNotification(index: number, value: NotificationConfig): void {
  notifications.value[index] = value
}

function addExchange(): void {
  exchanges.value.push({
    id: String(Date.now()),
    enable: true,
    name: '',
    apiKey: '',
    secret: '',
    description: ''
  })
}

function removeExchange(id: string): void {
  const index = exchanges.value.findIndex(e => e.id === id)
  if (index > -1) exchanges.value.splice(index, 1)
}

function updateExchange(index: number, value: ExchangeConfig): void {
  exchanges.value[index] = value
}

function getSectionBtnClass(section: SettingSection): string {
  return activeSection.value === section
    ? 'bg-indigo-600 text-white'
    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
}

// 保存设置
function handleSave() {
  emit('save', {
    accountName: accountName.value,
    notifications: notifications.value,
    exchanges: exchanges.value
  })
  console.log('保存设置:', {
    accountName: accountName.value,
    notifications: notifications.value,
    exchanges: exchanges.value
  })
}

// 页面激活时回调
const userDataStore = inject<userDataStore>('userDataStore')!
onActivated(() => {
  console.log('设置页面已激活',userDataStore)
  emit('activate')
})
</script>

<template>
  <div class="h-full flex flex-col p-4 overflow-hidden">
    <div class="bg-white rounded-lg shadow flex-1 flex flex-col overflow-hidden">
      <!-- 设置按钮区 -->
      <div class="px-4 py-4 border-b border-gray-200 flex gap-3">
        <button
          v-for="btn in SECTION_BUTTONS"
          :key="btn.key"
          @click="activeSection = btn.key"
          :class="['px-4 py-2 text-sm font-medium rounded-md transition-colors', getSectionBtnClass(btn.key)]"
        >
          {{ btn.label }}
        </button>
      </div>

      <!-- 设置内容区 -->
      <div class="flex-1 overflow-auto p-4">
        <!-- 账号信息 -->
        <div v-if="activeSection === 'account'" class="space-y-4">
          <div class="flex items-center gap-4">
            <label class="w-24 text-sm font-medium text-gray-700">账号名称</label>
            <input
              v-model="accountName"
              type="text"
              placeholder="请输入账号名称"
              class="flex-1 max-w-md px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
        </div>

        <!-- 通知设置 -->
        <div v-else-if="activeSection === 'notification'" class="space-y-4">
          <button
            @click="addNotification"
            class="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 transition-colors"
          >
            + 添加通知
          </button>
          <div class="space-y-3">
            <NotificationItem
              v-for="(item, index) in notifications"
              :key="item.id"
              :model-value="item"
              @update:model-value="updateNotification(index, $event)"
              @remove="removeNotification"
            />
          </div>
          <p v-if="notifications.length === 0" class="text-sm text-gray-500">
            暂无通知配置，点击上方按钮添加
          </p>
        </div>

        <!-- 交易所API -->
        <div v-else-if="activeSection === 'exchange'" class="space-y-4">
          <button
            @click="addExchange"
            class="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 transition-colors"
          >
            + 添加交易所
          </button>
          <div class="space-y-3">
            <ExchangeItem
              v-for="(item, index) in exchanges"
              :key="item.id"
              :model-value="item"
              @update:model-value="updateExchange(index, $event)"
              @remove="removeExchange"
            />
          </div>
          <p v-if="exchanges.length === 0" class="text-sm text-gray-500">
            暂无交易所配置，点击上方按钮添加
          </p>
        </div>
      </div>

      <!-- 保存按钮区 -->
      <div class="px-4 py-4 border-t border-gray-200">
        <button
          @click="handleSave"
          class="w-full px-4 py-3 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition-colors shadow-md"
        >
          保存设置
        </button>
      </div>
    </div>
  </div>
</template>
