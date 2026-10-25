<script setup lang="ts">
import type { MenuItem } from './types'
import { userDataStore } from './types/userDataStore'
import { ref, onMounted, provide } from 'vue'
import { postMessage } from './utils/common'
import uiSidebar from './components/uiSidebar.vue'
import uiMainContent from './components/uiMainContent.vue'
import { eMsg, eMenuId } from "./types"


// 当前激活的菜单项（用于内容区显示）
const activeItem = ref<MenuItem | undefined>(undefined)
// 侧边栏组件引用
const sidebarRef = ref<InstanceType<typeof uiSidebar> | null>(null)
// 用户数据
const user = new userDataStore()
// 当前页面从服务器获取的数据
const pageData = ref<any>(null)
provide('userDataStore', user)
provide('sidebarRef', sidebarRef)
provide('pageData', pageData)
onMounted(async () => {
  console.log("~~~~~~app.init~~~~~~~~~~")
  const response = await postMessage(eMsg.eWebInit)
  if (response.received?.args) {
    user.initFromServer(response.received.args)
    const resUser = response.received.args.user
    sidebarRef.value?.init(resUser.userName || 'admin')
    // console.log("~~~App.vue init~~~", resUser.page)
    const page = resUser.page//resUser.userName !== '' ? eMenuId.eMarket : eMenuId.eSettings
    sidebarRef.value?.setItem(page)
    if (page !== eMenuId.eSettings)
      sidebarRef.value?.setLock(false)
  }
})

// 处理菜单选择通知
const handleSelect = async (item: MenuItem) => {
  activeItem.value = item
  // 行情页在激活时自行请求 1001（币种列表），设置页无需页面数据
  if (item.id === eMenuId.eSettings || item.id === eMenuId.eMarket)
    return
  const response = await postMessage(1000 + item.id)
  pageData.value = response.received?.args ?? null
}
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-paper text-ink">
    <uiSidebar ref="sidebarRef" @select-item="handleSelect" />
    <uiMainContent v-if="activeItem" :active-item="activeItem" />
    <main v-else class="flex flex-1 items-center justify-center bg-paper">
      <div class="flex flex-col items-center gap-3 text-ink-soft">
        <i class="ri-loader-4-line animate-spin text-2xl"></i>
        <span class="text-sm tracking-wide">正在连接量化服务…</span>
      </div>
    </main>
  </div>
</template>
