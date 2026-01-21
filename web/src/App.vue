<script setup lang="ts">
import type { MenuItem } from './types'
import { userDataStore } from './types/userDataStore'
import { ref,onMounted,provide} from 'vue'
import { postMessage } from './utils/common'
import uiSidebar from './components/uiSidebar.vue'
import uiMainContent from './components/uiMainContent.vue'


// 当前激活的菜单项（用于内容区显示）
const activeItem = ref<MenuItem | undefined>(undefined)

// 侧边栏组件引用
const sidebarRef = ref<InstanceType<typeof uiSidebar> | null>(null)

// 处理菜单选择通知
const handleSelect = async (item: MenuItem) => {
  activeItem.value = item
  console.log('切换菜单项', item)
}
  // 演示：发送菜单切换事件到后端
  // try {
  //   await sendToBackend(item.id, { action: 'menu_select', menuName: item.name })
  //   console.log('已通知后端切换菜单')
  // } catch (error) {
  //   console.error('通知后端失败:', error)
  // }
  // const back = await postMessage(1001, item.id, { action: 'menu_select', menuName: item.name })
  // console.log("~~~按钮back~~~",back)

// 将用户数据注入子组件
const user = new userDataStore()
provide('userDataStore', user)
// init
onMounted(async () => {
  const data = await postMessage(1001)
  console.log("~~~App.vue init~~~",data)
})
</script>

<template>
  <!-- 外层布局容器 -->
  <div class="flex h-screen overflow-hidden bg-gray-50 text-gray-800">

    <!-- 左侧侧边栏 -->
    <uiSidebar
      ref="sidebarRef"
      @select-item="handleSelect"
    />

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

html, body, #app {
  height: 100%;
  width: 100%;
  overflow: hidden;
}
</style>