<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Sidebar from './components/uiSidebar.vue'
import MainContent from './components/uiMainContent.vue'
import {postMessage,sendMessage } from './utils/common'

// 定义菜单项类型
interface MenuItem {
  id: number
  name: string
  icon: string
}

// 定义菜单数据
const menuItems: MenuItem[] = [
  { id: 1, name: '行  情', icon: 'ri-dashboard-line' },
  { id: 2, name: '策  略', icon: 'ri-user-settings-line' },
  { id: 3, name: '回  测', icon: 'ri-file-list-3-line' },
  { id: 4, name: '订  单', icon: 'ri-pie-chart-2-line' },
  { id: 5, name: '设  置', icon: 'ri-settings-3-line' },
]

// Sidebar 组件引用
const sidebarRef = ref<InstanceType<typeof Sidebar> | null>(null)
const activeItem = ref<MenuItem | undefined>(undefined)

const handleSelect = async (item: MenuItem) => {
  activeItem.value = item
  console.log('切换菜单项', item)
  
  // 演示：发送菜单切换事件到后端
  // try {
  //   await sendToBackend(item.id, { action: 'menu_select', menuName: item.name })
  //   console.log('已通知后端切换菜单')
  // } catch (error) {
  //   console.error('通知后端失败:', error)
  // }
  // const back = await postMessage(1001, item.id, { action: 'menu_select', menuName: item.name })
  // console.log("~~~按钮back~~~",back)
}

// 组件挂载时初始化
onMounted(async () => {
  console.log('=== 系统初始化 ===')
  
  // 1. 初始化 activeItem
  activeItem.value = menuItems[1]
  
  // 2. 消息测试
  // let backdata = await postMessage(1000)
  // console.log('~~~~~postMessage:~~~~~~~~~', backdata)
  // backdata = await sendMessage(1003)
  // console.log('~~~~sendMessage:~~~~', backdata)

  // 3. 初始化侧边栏
  if (sidebarRef.value) {
    sidebarRef.value.init('sss')
    console.log('侧边栏初始化完成')
  }
})
</script>

<template>
  <!-- 外层布局容器 -->
  <div class="flex h-screen overflow-hidden bg-gray-50 text-gray-800">
    
    <!-- 左侧侧边栏 -->
    <Sidebar 
      v-if="activeItem"
      ref="sidebarRef"
      :menu-items="menuItems" 
      :active-item="activeItem" 
      @select-item="handleSelect" 
    />

    <!-- 右侧内容区 -->
    <MainContent v-if="activeItem" :active-item="activeItem" />
    
  </div>
</template>

<style>
/* 全局字体设置，也可以放在 index.css 中 */
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  margin: 0;
  padding: 0;
}

html, body, #app {
  height: 100%;
  width: 100%;
  overflow: hidden;
}
</style>