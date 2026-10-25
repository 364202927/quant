<script setup lang="ts">
import { ref, inject, onActivated, watch, computed } from 'vue'
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
const inputClass = 'w-full max-w-md rounded-lg border border-paper-line bg-paper px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/20'

const activeSectionLabel = computed(() => {
  const section = SECTION_BUTTONS.find(btn => btn.key === activeSection.value)
  return section?.label ?? ''
})

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
function sectionButtonClass(section: SettingSectionKey): string {
  return activeSection.value === section
    ? 'bg-indigo-600 text-white shadow-sm'
    : 'text-ink-soft hover:bg-paper-deep hover:text-ink'
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
  <div class="page-body">
    <section class="panel flex h-full flex-col overflow-hidden lg:flex-row">
      <!-- 左侧分页导航 -->
      <aside class="shrink-0 border-b border-paper-line p-3 lg:w-52 lg:border-b-0 lg:border-r">
        <div class="px-2 pb-3 pt-1">
          <h2 class="panel-title">设置</h2>
          <p class="mt-0.5 text-[11px] text-ink-faint">连接与账户配置</p>
        </div>
        <div class="flex gap-2 overflow-x-auto lg:flex-col">
          <button v-for="btn in SECTION_BUTTONS" :key="btn.key" @click="activeSection = btn.key"
            :class="['shrink-0 rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors lg:w-full', sectionButtonClass(btn.key)]">
            {{ btn.label }}
          </button>
        </div>
        <p class="mt-4 hidden rounded-lg border border-paper-line bg-paper p-3 text-[11px] leading-relaxed text-ink-soft lg:block">
          修改后点击「保存设置」同步到服务端；首次配置账号时会解锁工作台菜单。
        </p>
      </aside>

      <!-- 右侧内容 -->
      <div class="flex min-h-0 min-w-0 flex-1 flex-col">
        <header class="shrink-0 border-b border-paper-line px-5 py-4">
          <h2 class="text-sm font-semibold text-ink">{{ activeSectionLabel }}</h2>
          <p class="mt-0.5 text-xs text-ink-soft">{{ activeSection === 'account' ? '维护账户名称与运行偏好' : '管理用于通知、交易与 AI 服务的连接凭据' }}</p>
        </header>

        <!-- 设置内容区 -->
        <div class="flex-1 overflow-auto p-5">
          <!-- 账号信息 -->
          <div v-if="activeSection === 'account'" class="max-w-xl space-y-4">
            <div class="flex items-center gap-4">
              <label class="w-24 shrink-0 text-sm font-medium text-ink-soft">{{ TEXT_MAP.settings_account_name_label }}</label>
              <input v-model="accountName" type="text" :placeholder="TEXT_MAP.settings_account_name_placeholder"
                :class="inputClass" />
            </div>
            <div class="flex items-center gap-4">
              <label class="w-24 shrink-0 text-sm font-medium text-ink-soft">CCXT重试次数</label>
              <input v-model.number="ccxtRetry" type="number" :class="inputClass" />
            </div>
            <div class="flex items-center gap-4">
              <label class="w-24 shrink-0 text-sm font-medium text-ink-soft">控制台启用</label>
              <input v-model="consoleEnable" type="checkbox"
                class="h-4 w-4 rounded border-paper-line accent-indigo-600 focus:ring-indigo-500" />
            </div>
            <div class="flex items-center gap-4">
              <label class="w-24 shrink-0 text-sm font-medium text-ink-soft">Telegram启用</label>
              <input v-model="tgEnable" type="checkbox" class="h-4 w-4 rounded border-paper-line accent-indigo-600 focus:ring-indigo-500" />
            </div>
          </div>

          <!-- 通知设置 -->
          <div v-else-if="activeSection === 'notification'" class="space-y-4">
            <button @click="addUnit('notification')"
              class="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700">
              <i class="ri-add-line"></i>
              {{ SETTINGS_CONFIG.notification.addBtnText }}通知
            </button>
            <div class="space-y-3">
              <SettingItem v-for="(item, index) in notifications" :key="index" item-type="notification"
                :model-value="item" @update:model-value="checkItem('newsletter', index, $event)"
                @remove="removeUnit($event, 'notification')" />
            </div>
            <p v-if="notifications.length === 0" class="text-sm text-ink-faint">
              {{ TEXT_MAP.settings_notification_empty }}
            </p>
          </div>

          <!-- 交易所API -->
          <div v-else-if="activeSection === 'exchange'" class="space-y-4">
            <button @click="addUnit('exchange')"
              class="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700">
              <i class="ri-add-line"></i>
              {{ SETTINGS_CONFIG.exchange.addBtnText }}交易所
            </button>
            <div class="space-y-3">
              <SettingItem v-for="(item, index) in exchanges" :key="index" item-type="exchange" :model-value="item"
                @update:model-value="checkItem('exchange', index, $event)" @remove="removeUnit($event, 'exchange')" />
            </div>
            <p v-if="exchanges.length === 0" class="text-sm text-ink-faint">
              {{ TEXT_MAP.settings_exchange_empty }}
            </p>
          </div>

          <!-- AI API -->
          <div v-else-if="activeSection === 'ai'" class="space-y-4">
            <button @click="addUnit('ai')"
              class="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700">
              <i class="ri-add-line"></i>
              {{ SETTINGS_CONFIG.ai.addBtnText }}AI 接口
            </button>
            <div class="space-y-3">
              <SettingItem v-for="(item, index) in ais" :key="index" item-type="ai" :model-value="item"
                @update:model-value="checkItem('ai', index, $event)" @remove="removeUnit($event, 'ai')" />
            </div>
            <p v-if="ais.length === 0" class="text-sm text-ink-faint">
              {{ TEXT_MAP.settings_ai_empty }}
            </p>
          </div>
        </div>

        <!-- 保存按钮区 -->
        <footer class="flex shrink-0 items-center justify-between gap-3 border-t border-paper-line px-5 py-3.5">
          <p class="hidden text-xs text-ink-faint sm:block">配置保存在本地服务端，可随时修改</p>
          <button @click="handleSave"
            class="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-indigo-700">
            <i class="ri-save-3-line"></i>
            {{ TEXT_MAP.btn_save }}
          </button>
        </footer>
      </div>
    </section>
  </div>
</template>
