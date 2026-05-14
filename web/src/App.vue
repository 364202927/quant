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
  const response = await postMessage(eMsg.eWebInit)
  if (response.received?.args) {
    user.initFromServer(response.received.args)
    const resUser = response.received.args.user
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
  if (item.id !== eMenuId.eSettings) {
    const response = await postMessage(1000 + item.id)
    pageData.value = response.received?.args ?? null
  }
}
</script>

<template>
  <!-- 外层布局容器 -->
  <div class="flex h-screen overflow-hidden bg-gray-50 text-gray-800">
    <!-- 左侧侧边栏 -->
    <uiSidebar ref="sidebarRef" @select-item="handleSelect" />
    <!-- 右侧内容区 -->
    <uiMainContent v-if="activeItem" :active-item="activeItem" />
  </div>
</template>

<style>
/* 全局字体设置，也可以放在 index.css 中 */
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  margin: 0;
  padding: 0;
}

html,
body,
#app {
  height: 100%;
  width: 100%;
  overflow: hidden;
}
</style>