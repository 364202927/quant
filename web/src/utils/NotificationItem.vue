<script setup lang="ts">
import type { NotificationConfig } from '../types'

interface Props {
  modelValue: NotificationConfig
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:modelValue': [value: NotificationConfig]
  remove: [id: string]
}>()

function updateField<K extends keyof NotificationConfig>(field: K, value: NotificationConfig[K]): void {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}
</script>

<template>
  <div class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
    <input
      type="checkbox"
      :checked="modelValue.enable"
      @change="updateField('enable', ($event.target as HTMLInputElement).checked)"
      class="w-4 h-4 text-indigo-600 rounded focus:ring-indigo-500"
    />
    <input
      type="text"
      :value="modelValue.token"
      @input="updateField('token', ($event.target as HTMLInputElement).value)"
      placeholder="Token"
      class="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
    />
    <input
      type="text"
      :value="modelValue.chatId"
      @input="updateField('chatId', ($event.target as HTMLInputElement).value)"
      placeholder="Chat ID"
      class="w-32 px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
    />
    <button
      @click="emit('remove', modelValue.id)"
      class="p-2 text-red-500 hover:text-red-700 hover:bg-red-50 rounded-md transition-colors"
    >
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
      </svg>
    </button>
  </div>
</template>
