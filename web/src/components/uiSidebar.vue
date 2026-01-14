<script setup>
  defineProps({
    menuItems: {
      type: Array,
      required: true
    },
    activeItem: {
      type: Object,
      required: true
    }
  })
  
  const emit = defineEmits(['select-item'])
  
  const onSelect = (item) => {
    emit('select-item', item)
  }
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
          <li v-for="(item, index) in menuItems" :key="index">
            <button 
              @click="onSelect(item)"
              class="w-full flex items-center px-6 py-3 text-sm transition-all duration-200 border-l-4"
              :class="[
                activeItem.id === item.id 
                  ? 'bg-transparent border-indigo-500 text-blue-400 hover:text-blue-500 font-medium' 
                  // : 'border-transparent text-gray-400 hover:bg-gray-800 hover:text-white'
                  : 'bg-transparent text-white hover:text-white'
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
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center">
            <i class="ri-user-line"></i>
          </div>
          <div>
            <p class="text-sm font-medium">管理员</p>
            <p class="text-xs text-gray-500">admin@test.com</p>
          </div>
        </div>
      </div>
    </aside>
  </template>