<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Sidebar from './components/uiSidebar.vue'
import MainContent from './components/uiMainContent.vue'
import { readJson, writeJson, fileExists, localStorage, downloadJson, uploadJson } from './utils/common'

// 定义菜单数据
const menuItems = [
  { id: 1, name: '市场行情', icon: 'ri-dashboard-line' },
  { id: 2, name: '设置', icon: 'ri-user-settings-line' },
  { id: 3, name: '订单列表', icon: 'ri-file-list-3-line' },
  { id: 4, name: '回测分析', icon: 'ri-pie-chart-2-line'  },
]

// 当前选中的项
const activeItem = ref(menuItems[1])

// 处理子组件触发的切换事件
const handleSelect = (item: any) => {
  activeItem.value = item
}

// 组件挂载时演示工具函数的使用
onMounted(async () => {
  console.log('=== 通用工具函数测试 ===')
  
  // 1. 测试 localStorage 读写
  console.log('1. 测试 localStorage')
  localStorage.setJson('userConfig', { theme: 'dark', language: 'zh-CN' })
  const config = localStorage.getJson('userConfig')
  console.log('读取的配置:', config)
  
  // 2. 测试文件是否存在
  console.log('\n2. 测试文件存在性检查')
  const exists = await fileExists('/vite.svg')
  console.log('/vite.svg 是否存在:', exists)
  
  // 3. 测试读取 JSON 文件（如果 public 目录有 config.json）
  console.log('\n3. 尝试读取 JSON 文件')
  try {
    // 注意：这个文件需要先在 public 目录创建
    const jsonData = await readJson('/config.json')
    console.log('读取的 JSON 数据:', jsonData)
  } catch (error) {
    console.log('读取失败（文件可能不存在）:', error)
  }
  
  // 4. 演示数据导出功能（注释掉，避免自动下载）
  // downloadJson({ test: 'data', timestamp: Date.now() }, 'export.json')
  
  console.log('\n=== 工具函数已就绪，可以在控制台使用 ===')
  console.log('可用函数: readJson, writeJson, fileExists, localStorage, downloadJson, uploadJson')
})
</script>

<template>
  <!-- 外层布局容器 -->
  <div class="flex h-screen overflow-hidden bg-gray-50 text-gray-800">
    
    <!-- 左侧侧边栏 -->
    <Sidebar 
      :menu-items="menuItems" 
      :active-item="activeItem" 
      @select-item="handleSelect" 
    />

    <!-- 右侧内容区 -->
    <MainContent :active-item="activeItem" />
    
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