<script setup>
  defineProps({
    activeItem: {
      type: Object,
      required: true
    }
  })
  </script>
  
  <template>
    <main class="flex-1 flex flex-col min-w-0 overflow-hidden relative">
      
      <!-- 顶部 Header -->
      <header class="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-8 shadow-sm shrink-0">
        <h2 class="text-xl font-bold text-gray-800">{{ activeItem.name }}</h2>
        <div class="flex items-center gap-4">
          <button class="p-2 text-gray-400 hover:text-gray-600 transition">
            <i class="ri-notification-3-line text-xl"></i>
          </button>
        </div>
      </header>
  
      <!-- 内容显示区 -->
      <div class="flex-1 p-8 overflow-y-auto">
        <div class="max-w-4xl mx-auto">
          
          <transition name="fade" mode="out-in">
            <div :key="activeItem.id" class="bg-white rounded-xl shadow-sm border border-gray-200 p-10 flex flex-col items-center justify-center min-h-[400px]">
              
              <!-- 显示大标题图标 -->
              <div class="w-20 h-20 bg-indigo-50 rounded-full flex items-center justify-center mb-6 text-indigo-600">
                <i :class="[activeItem.icon, 'text-4xl']"></i>
              </div>
  
              <!-- 动态标题 -->
              <h1 class="text-3xl font-bold text-gray-900 mb-4">
                当前页面：{{ activeItem.name }}
              </h1>
              
              <p class="text-gray-500 text-center max-w-md mb-8">
                您现在位于“{{ activeItem.name }}”模块。左侧点击切换，这里会同步更新内容，且字体风格保持一致。
              </p>
  
              <!-- 按钮组 -->
              <div class="flex gap-4">
                <button class="px-6 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition shadow-lg shadow-indigo-500/30 font-medium flex items-center gap-2">
                  <i :class="activeItem.icon"></i>
                  新建 {{ activeItem.name }}
                </button>
                <button class="px-6 py-2.5 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition font-medium">
                  查看 {{ activeItem.name }} 详情
                </button>
              </div>
  
            </div>
          </transition>
  
        </div>
      </div>
  
    </main>
  </template>
  
  <style scoped>
  /* 过渡动画 */
  .fade-enter-active, .fade-leave-active {
    transition: opacity 0.3s ease;
  }
  .fade-enter-from, .fade-leave-to {
    opacity: 0;
  }
  </style>