<script setup lang="ts">
import type { newsletter, markets, ai } from '../../types/userDataStore'

type ItemType = 'notification' | 'exchange' | 'ai'
type ItemData = newsletter | markets | ai

interface Props {
  itemType: ItemType
  modelValue: ItemData
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:modelValue': [value: ItemData]
  remove: [id: string]
}>()

function updateField(field: string, value: any): void {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}

// 删除按钮 SVG
const deleteIcon = `M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16`

// 输入框通用样式
const inputClass = 'px-3 py-2 text-sm bg-gray-100 text-black border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500'
</script>

<template>
  <!-- Notification 类型 -->
  <div v-if="itemType === 'notification'" class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
    <input type="text" :value="(modelValue as newsletter).id"
      @input="updateField('id', ($event.target as HTMLInputElement).value)" placeholder="ID"
      :class="[inputClass, 'w-32']" />
    <input type="text" :value="(modelValue as newsletter).token"
      @input="updateField('token', ($event.target as HTMLInputElement).value)" placeholder="Token"
      :class="[inputClass, 'flex-1']" />
    <input type="text" :value="(modelValue as newsletter).value1"
      @input="updateField('value1', ($event.target as HTMLInputElement).value)" placeholder="Value 1"
      :class="[inputClass, 'w-32']" />
    <input type="text" :value="(modelValue as newsletter).value2"
      @input="updateField('value2', ($event.target as HTMLInputElement).value)" placeholder="Value 2"
      :class="[inputClass, 'w-32']" />
    <button @click="emit('remove', modelValue.id)"
      class="p-2 text-red-500 hover:text-red-700 hover:bg-red-50 rounded-md transition-colors">
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="deleteIcon" />
      </svg>
    </button>
  </div>

  <!-- Exchange 类型 -->
  <div v-else-if="itemType === 'exchange'" class="p-4 bg-gray-50 rounded-lg border border-gray-200 space-y-3">
    <div class="flex items-center gap-3">
      <input type="checkbox" :checked="(modelValue as markets).enable"
        @change="updateField('enable', ($event.target as HTMLInputElement).checked)"
        class="w-4 h-4 text-indigo-600 rounded focus:ring-indigo-500" />
      <input type="text" :value="(modelValue as markets).id"
        @input="updateField('id', ($event.target as HTMLInputElement).value)" placeholder="ID"
        :class="[inputClass, 'w-32']" />
      <input type="text" :value="(modelValue as markets).exchange"
        @input="updateField('exchange', ($event.target as HTMLInputElement).value)" placeholder="交易所名称"
        :class="[inputClass, 'w-40']" />
      <input type="text" :value="(modelValue as markets).description"
        @input="updateField('description', ($event.target as HTMLInputElement).value)" placeholder="描述"
        :class="[inputClass, 'flex-1']" />
      <button @click="emit('remove', modelValue.id)"
        class="p-2 text-red-500 hover:text-red-700 hover:bg-red-50 rounded-md transition-colors">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="deleteIcon" />
        </svg>
      </button>
    </div>
    <div class="flex gap-3 pl-7">
      <input type="text" :value="(modelValue as markets).apiKey"
        @input="updateField('apiKey', ($event.target as HTMLInputElement).value)" placeholder="API Key"
        :class="[inputClass, 'flex-1 font-mono']" />
      <input type="password" :value="(modelValue as markets).secret"
        @input="updateField('secret', ($event.target as HTMLInputElement).value)" placeholder="Secret"
        :class="[inputClass, 'flex-1 font-mono']" />
    </div>
  </div>

  <!-- AI 类型 -->
  <div v-else-if="itemType === 'ai'" class="p-4 bg-gray-50 rounded-lg border border-gray-200 space-y-3">
    <div class="flex items-center gap-3">
      <input type="text" :value="(modelValue as ai).id"
        @input="updateField('id', ($event.target as HTMLInputElement).value)" placeholder="ID"
        :class="[inputClass, 'w-32']" />
      <input type="text" :value="(modelValue as ai).url"
        @input="updateField('url', ($event.target as HTMLInputElement).value)" placeholder="API URL"
        :class="[inputClass, 'flex-1']" />
      <button @click="emit('remove', modelValue.id)"
        class="p-2 text-red-500 hover:text-red-700 hover:bg-red-50 rounded-md transition-colors">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="deleteIcon" />
        </svg>
      </button>
    </div>
    <div class="flex gap-3 pl-7">
      <input type="text" :value="(modelValue as ai).token"
        @input="updateField('token', ($event.target as HTMLInputElement).value)" placeholder="API Token"
        :class="[inputClass, 'flex-1 font-mono']" />
    </div>
  </div>
</template>
