<script setup>
  defineProps({
    activeItem: {
      type: Object,
      required: true
    }
  })
  </script>
  
  <template>
    <main class="flex-1 flex flex-col min-w-0 overflow-hidden relative bg-yellow-50">
      
      <!-- 顶部 标题 -->
      <header class="h-16 bg-white border-b border-gray-200 flex items-center justify-center px-8 shadow-sm shrink-0">
        <h2 class="text-xl font-bold text-gray-800">{{ activeItem.name }}</h2>
      </header>
  
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