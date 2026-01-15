<script setup lang="ts">
import { ref } from 'vue'

interface MenuItem {
  id: number
  name: string
  icon: string
}

defineProps<{
  menuItems: MenuItem[]
  activeItem: MenuItem
}>()

const emit = defineEmits<{
  'select-item': [item: MenuItem]
}>()

// 用户名
const userName = ref<string>('')

// 按钮是否禁用
const isDisabled = ref<boolean>(true)

// 初始化函数
const init = (strName: string) => {
  userName.value = strName
  isDisabled.value = false // 初始化完成后启用按钮
}

// 选择菜单项
const onSelect = (item: MenuItem) => {
  if (isDisabled.value) return
  emit('select-item', item)
}

// 设置按钮点击（不受禁用限制）
const onSettingsClick = () => {
  emit('select-item', { id: 5, name: '设置', icon: 'ri-settings-3-line' })
}

// 获取用户名首字母
const getUserInitial = () => {
  return userName.value ? userName.value.charAt(0).toUpperCase() : '?'
}

// 暴露 init 方法给父组件调用
defineExpose({
  init
})
</script>
  
  <template>
    <aside class="w-64 bg-gray-900 text-white flex flex-col shadow-2xl z-10 shrink-0">
      <!-- Logo 区域 -->
      <div class="h-16 flex items-center px-6 border-b border-gray-800">
        <div class="w-8 h-8 bg-indigo-500 rounded-md flex items-center justify-center mr-3">
          <i class="ri-code-s-slash-line text-lg"></i>
        </div>
        <span class="text-lg font-bold tracking-wide">Dashboard</span>
      </div>
  
      <!-- 菜单列表 -->
      <nav class="flex-1 overflow-y-auto py-4">
        <ul class="space-y-1">
          <li v-for="(item, index) in menuItems.filter(i => i.id !== 5)" :key="index">
            <button 
              @click="onSelect(item)"
              :disabled="isDisabled"
              class="w-full flex items-center px-6 py-3 text-sm transition-all duration-200 border-l-4"
              :class="[
                activeItem.id === item.id 
                  ? 'bg-transparent border-indigo-500 text-blue-400 hover:text-blue-500 font-medium' 
                  : 'bg-transparent text-white hover:text-white',
                isDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
              ]"
            >
              <i :class="[item.icon, 'mr-3 text-lg']"></i>
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
              <p class="text-sm font-medium truncate">{{ userName }}</p>
              <!-- <p class="text-xs text-gray-500">在线</p> -->
            </div>
          </div>
          <!-- 设置按钮 - 使用图片 -->
          <button
            @click="onSettingsClick"
            class="w-13 h-13 flex items-center justify-center overflow-visible opacity-70 hover:opacity-100 transition-opacity cursor-pointer flex-shrink-0"
            :class="[
              activeItem.id === 5 ? 'opacity-100' : ''
            ]"
          >
            <img 
              src="/setting.png"
              alt="设置"
              class="w-10 h-10 object-cover"
            />
          </button>
        </div>
      </div>
    </aside>
  </template>