<script setup lang="ts">
import { ref, inject, onActivated, watch } from 'vue'
import SettingItem from './settingItem.vue'
import type { newsletter, markets, ai } from '../../types/userDataStore'
import type { userDataStore } from '../../types/userDataStore'
import { TEXT_MAP } from '../../config/textMap'

// 设置项配置类型
type SettingSectionKey = 'account' | 'notification' | 'exchange' | 'ai'

// 统一的设置项配置（不包括 account）
const SETTINGS_CONFIG = {
  notification: {
    key: 'notification' as const,
    label: '通知API',
    addBtnText: '添加',
    dataKey: 'notifications' as const,
    storeKey: 'notifs' as const,
    checkItemKey: 'newsletter' as const,
    defaultItem: (): newsletter => ({
      id: '',
      token: '',
      value1: '',
      value2: ''
    })
  },
  exchange: {
    key: 'exchange' as const,
    label: '交易所API',
    addBtnText: '添加',
    dataKey: 'exchanges' as const,
    storeKey: 'exchanges' as const,
    checkItemKey: 'exchange' as const,
    defaultItem: (): markets => ({
      id: '',
      enable: true,
      exchange: '',
      apiKey: '',
      secret: '',
      description: ''
    })
  },
  ai: {
    key: 'ai' as const,
    label: 'AI API',
    addBtnText: '添加',
    dataKey: 'ais' as const,
    storeKey: 'ais' as const,
    checkItemKey: 'ai' as const,
    defaultItem: (): ai => ({
      id: '',
      token: '',
      url: ''
    })
  }
}

// 完整的 SECTION_BUTTONS 配置（包括 account）
const SECTION_BUTTONS = [
  { key: 'account' as const, label: '账号信息' },
  SETTINGS_CONFIG.notification,
  SETTINGS_CONFIG.exchange,
  SETTINGS_CONFIG.ai
] as const

const activeSection = ref<SettingSectionKey>('account')
const accountName = ref('')
const ccxtRetry = ref(3)
const consoleEnable = ref(true)
const tgEnable = ref(false)
const notifications = ref<newsletter[]>([])
const exchanges = ref<markets[]>([])
const ais = ref<ai[]>([])
const store = inject<userDataStore>('userDataStore')!
const sidebarRef = inject<any>('sidebarRef')

type ListSectionKey = Exclude<SettingSectionKey, 'account'>

// 数据映射，用于通用函数访问
const dataMap = {
  notifications,
  exchanges,
  ais
}

// checkItem 的 page 参数到 dataKey 的映射
const checkItemKeyToDataKey: Record<string, keyof typeof dataMap> = {
  newsletter: 'notifications',
  exchange: 'exchanges',
  ai: 'ais'
}

// 获取指定 section 对应的本地数组引用
function getSectionData(sectionKey: ListSectionKey) {
  const config = SETTINGS_CONFIG[sectionKey]
  return dataMap[config.dataKey]
}

// 创建 添加item控件
function addUnit(sectionKey: ListSectionKey): void {
  // console.log("添加控件", sectionKey)
  if (!validateAndSaveCurrentSection()) {
    alert('请先填写完整的 ID 再添加新项')
    return
  }
  const config = SETTINGS_CONFIG[sectionKey]
  getSectionData(sectionKey).value.push(config.defaultItem() as any)
}

function removeUnit(id: string, sectionKey: ListSectionKey): void {
  const data = getSectionData(sectionKey)
  const index = data.value.findIndex((item: any) => item.id === id)
  if (index > -1) {
    data.value.splice(index, 1)
    store.deleteApi(SETTINGS_CONFIG[sectionKey].storeKey, id)
  }
}

// 监听 item 更新，只更新本地数组，不保存到 store
function checkItem(page: string, index: number, value: newsletter | markets | ai): void {
  // console.log('~~~updateItem~', page, index, value)
  const dataKey = checkItemKeyToDataKey[page]
  if (dataKey) {
    ; (dataMap[dataKey].value as any[])[index] = value
  }
}

// 验证并保存当前分页的数据到 store
function validateAndSaveCurrentSection(): boolean {
  const section = activeSection.value
  if (section === 'account') {
    store.setUser({
      userName: accountName.value,
      ccxtRetry: ccxtRetry.value,
      console_e: consoleEnable.value,
      tg_e: tgEnable.value
    })
    console.log('账号信息已保存到 store')
    return true
  }

  // notification / exchange / ai 统一处理
  const config = SETTINGS_CONFIG[section]
  const items = getSectionData(section).value as { id: string }[]
  if (items.some(item => !item.id || item.id.trim() === ''))
    return false
  items.forEach(item => {
    store.setApi(config.storeKey, item.id, item as newsletter | markets | ai)
  })
  console.log(`${config.label}数据已保存到 store`)
  return true
}

// 从 store 加载指定分页的数据
function loadSectionData(section: SettingSectionKey): void {
  // console.log("~~~~~~~~加载分页数据~~~~~~~~~~", section)
  if (section === 'account') {
    const userData = store.getMapByKey('') as any
    accountName.value = userData.userName
    ccxtRetry.value = userData.ccxtRetry
    consoleEnable.value = userData.console_e
    tgEnable.value = userData.tg_e
    return
  }

  // notification / exchange / ai 统一处理
  const config = SETTINGS_CONFIG[section]
  const storeMap = store.getMapByKey(config.storeKey) as Map<string, any>
  getSectionData(section).value = Array.from(storeMap.values())
}

// 返回选中样式
function chectSelect(section: SettingSectionKey): string {
  return activeSection.value === section
    ? 'bg-indigo-600 text-white'
    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
}

// 监听 activeSection 变化，自动加载对应数据
watch(activeSection, (newSection) => {
  // 切换分页前，先验证并保存当前分页的数据
  validateAndSaveCurrentSection()
  // 加载新分页的数据
  loadSectionData(newSection)
})

// 同步设置
function handleSave() {
  if (!validateAndSaveCurrentSection()) {
    alert('请先填写完整的 ID')
    return
  }
  store.update2Server()
  sidebarRef?.value?.setLock(false)
}

// 页面激活时回调
onActivated(() => {
  console.log('设置页面已激活', store)
  // 加载当前分页的数据
  loadSectionData(activeSection.value)
})
</script>

<template>
  <div class="h-full flex flex-col p-4 overflow-hidden">
    <div class="bg-white rounded-lg shadow flex-1 flex flex-col overflow-hidden">
      <!-- tab按钮区 -->
      <div class="px-4 py-4 border-b border-gray-200 flex gap-3">
        <button v-for="btn in SECTION_BUTTONS" :key="btn.key" @click="activeSection = btn.key"
          :class="['px-4 py-2 text-sm font-medium rounded-md transition-colors', chectSelect(btn.key)]">
          {{ btn.label }}
        </button>
      </div>

      <!-- 设置内容区 -->
      <div class="flex-1 overflow-auto p-4">
        <!-- 账号信息 -->
        <div v-if="activeSection === 'account'" class="space-y-4">
          <div class="flex items-center gap-4">
            <label class="w-24 text-sm font-medium text-gray-700">{{ TEXT_MAP.settings_account_name_label }}</label>
            <input v-model="accountName" type="text" :placeholder="TEXT_MAP.settings_account_name_placeholder"
              class="flex-1 max-w-md px-3 py-2 text-sm bg-gray-100 text-black border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500" />
          </div>
          <div class="flex items-center gap-4">
            <label class="w-24 text-sm font-medium text-gray-700">CCXT重试次数</label>
            <input v-model.number="ccxtRetry" type="number"
              class="flex-1 max-w-md px-3 py-2 text-sm bg-gray-100 text-black border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500" />
          </div>
          <div class="flex items-center gap-4">
            <label class="w-24 text-sm font-medium text-gray-700">控制台启用</label>
            <input v-model="consoleEnable" type="checkbox"
              class="w-4 h-4 text-indigo-600 rounded focus:ring-indigo-500" />
          </div>
          <div class="flex items-center gap-4">
            <label class="w-24 text-sm font-medium text-gray-700">Telegram启用</label>
            <input v-model="tgEnable" type="checkbox" class="w-4 h-4 text-indigo-600 rounded focus:ring-indigo-500" />
          </div>
        </div>

        <!-- 通知设置 -->
        <div v-else-if="activeSection === 'notification'" class="space-y-4">
          <button @click="addUnit('notification')"
            class="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 transition-colors">
            {{ TEXT_MAP.prefix_add }} {{ SETTINGS_CONFIG.notification.addBtnText }}
          </button>
          <div class="space-y-3">
            <SettingItem v-for="(item, index) in notifications" :key="index" item-type="notification"
              :model-value="item" @update:model-value="checkItem('newsletter', index, $event)"
              @remove="removeUnit($event, 'notification')" />
          </div>
          <p v-if="notifications.length === 0" class="text-sm text-gray-500">
            {{ TEXT_MAP.settings_notification_empty }}
          </p>
        </div>

        <!-- 交易所API -->
        <div v-else-if="activeSection === 'exchange'" class="space-y-4">
          <button @click="addUnit('exchange')"
            class="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 transition-colors">
            {{ TEXT_MAP.prefix_add }} {{ SETTINGS_CONFIG.exchange.addBtnText }}
          </button>
          <div class="space-y-3">
            <SettingItem v-for="(item, index) in exchanges" :key="index" item-type="exchange" :model-value="item"
              @update:model-value="checkItem('exchange', index, $event)" @remove="removeUnit($event, 'exchange')" />
          </div>
          <p v-if="exchanges.length === 0" class="text-sm text-gray-500">
            {{ TEXT_MAP.settings_exchange_empty }}
          </p>
        </div>

        <!-- AI API -->
        <div v-else-if="activeSection === 'ai'" class="space-y-4">
          <button @click="addUnit('ai')"
            class="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 transition-colors">
            {{ TEXT_MAP.prefix_add }} {{ SETTINGS_CONFIG.ai.addBtnText }}
          </button>
          <div class="space-y-3">
            <SettingItem v-for="(item, index) in ais" :key="index" item-type="ai" :model-value="item"
              @update:model-value="checkItem('ai', index, $event)" @remove="removeUnit($event, 'ai')" />
          </div>
          <p v-if="ais.length === 0" class="text-sm text-gray-500">
            {{ TEXT_MAP.settings_ai_empty }}
          </p>
        </div>
      </div>

      <!-- 保存按钮区 -->
      <div class="px-4 py-4 border-t border-gray-200">
        <button @click="handleSave"
          class="w-full px-4 py-3 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition-colors shadow-md">
          {{ TEXT_MAP.btn_save }}
        </button>
      </div>
    </div>
  </div>
</template>
