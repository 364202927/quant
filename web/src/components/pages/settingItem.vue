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

// 输入框通用样式
const inputClass = 'rounded-lg border border-paper-line bg-paper-soft px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/20'

const removeButtonClass = 'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-rose-500 transition-colors hover:bg-rose-50 hover:text-rose-700'
</script>

<template>
  <!-- Notification 类型 -->
  <div v-if="itemType === 'notification'" class="flex flex-wrap items-center gap-3 rounded-xl border border-paper-line bg-paper p-3">
    <input type="text" :value="(modelValue as newsletter).id"
      @input="updateField('id', ($event.target as HTMLInputElement).value)" placeholder="ID"
      :class="[inputClass, 'w-32']" />
    <input type="text" :value="(modelValue as newsletter).token"
      @input="updateField('token', ($event.target as HTMLInputElement).value)" placeholder="Token"
      :class="[inputClass, 'min-w-40 flex-1']" />
    <input type="text" :value="(modelValue as newsletter).value1"
      @input="updateField('value1', ($event.target as HTMLInputElement).value)" placeholder="Value 1"
      :class="[inputClass, 'w-32']" />
    <input type="text" :value="(modelValue as newsletter).value2"
      @input="updateField('value2', ($event.target as HTMLInputElement).value)" placeholder="Value 2"
      :class="[inputClass, 'w-32']" />
    <button @click="emit('remove', modelValue.id)" :class="removeButtonClass" title="删除">
      <i class="ri-delete-bin-line text-base"></i>
    </button>
  </div>

  <!-- Exchange 类型 -->
  <div v-else-if="itemType === 'exchange'" class="space-y-3 rounded-xl border border-paper-line bg-paper p-4">
    <div class="flex flex-wrap items-center gap-3">
      <input type="checkbox" :checked="(modelValue as markets).enable"
        @change="updateField('enable', ($event.target as HTMLInputElement).checked)"
        class="h-4 w-4 rounded border-paper-line accent-indigo-600 focus:ring-indigo-500" />
      <input type="text" :value="(modelValue as markets).id"
        @input="updateField('id', ($event.target as HTMLInputElement).value)" placeholder="ID"
        :class="[inputClass, 'w-32']" />
      <input type="text" :value="(modelValue as markets).exchange"
        @input="updateField('exchange', ($event.target as HTMLInputElement).value)" placeholder="交易所名称"
        :class="[inputClass, 'w-40']" />
      <input type="text" :value="(modelValue as markets).description"
        @input="updateField('description', ($event.target as HTMLInputElement).value)" placeholder="描述"
        :class="[inputClass, 'min-w-40 flex-1']" />
      <button @click="emit('remove', modelValue.id)" :class="removeButtonClass" title="删除">
        <i class="ri-delete-bin-line text-base"></i>
      </button>
    </div>
    <div class="flex flex-wrap gap-3 pl-0 md:pl-7">
      <input type="text" :value="(modelValue as markets).apiKey"
        @input="updateField('apiKey', ($event.target as HTMLInputElement).value)" placeholder="API Key"
        :class="[inputClass, 'min-w-40 flex-1 font-mono']" />
      <input type="password" :value="(modelValue as markets).secret"
        @input="updateField('secret', ($event.target as HTMLInputElement).value)" placeholder="Secret"
        :class="[inputClass, 'min-w-40 flex-1 font-mono']" />
    </div>
  </div>

  <!-- AI 类型 -->
  <div v-else-if="itemType === 'ai'" class="space-y-3 rounded-xl border border-paper-line bg-paper p-4">
    <div class="flex flex-wrap items-center gap-3">
      <input type="text" :value="(modelValue as ai).id"
        @input="updateField('id', ($event.target as HTMLInputElement).value)" placeholder="ID"
        :class="[inputClass, 'w-32']" />
      <input type="text" :value="(modelValue as ai).url"
        @input="updateField('url', ($event.target as HTMLInputElement).value)" placeholder="API URL"
        :class="[inputClass, 'min-w-40 flex-1']" />
      <button @click="emit('remove', modelValue.id)" :class="removeButtonClass" title="删除">
        <i class="ri-delete-bin-line text-base"></i>
      </button>
    </div>
    <div class="flex flex-wrap gap-3 pl-0 md:pl-7">
      <input type="text" :value="(modelValue as ai).token"
        @input="updateField('token', ($event.target as HTMLInputElement).value)" placeholder="API Token"
        :class="[inputClass, 'min-w-40 flex-1 font-mono']" />
    </div>
  </div>
</template>
