# 通用工具函数库

## 📦 文件说明

`common.ts` - 包含前端常用的文件操作、JSON 处理和本地存储工具函数

---

## 🚀 使用方法

### 1. 导入函数

```typescript
import { readJson, writeJson, fileExists, localStorage, downloadJson, uploadJson } from '@/utils/common'
```

---

## 📖 API 文档

### readJson<T>(path: string): Promise<T>

读取 JSON 文件（从 public 目录或远程 URL）

**参数：**
- `path`: 文件路径

**返回：** `Promise<T>` - 解析后的 JSON 对象

**示例：**
```typescript
// 读取 public 目录下的文件
const config = await readJson('/config.json')

// 读取远程 JSON
const data = await readJson('http://localhost:8000/api/data')
```

---

### writeJson<T>(path: string, data: T): Promise<boolean>

写入 JSON 文件（通过后端 API）

**参数：**
- `path`: API 端点路径
- `data`: 要写入的数据

**返回：** `Promise<boolean>` - 是否成功

**示例：**
```typescript
const success = await writeJson('http://localhost:8000/api/save', {
  name: 'test',
  value: 123
})
```

---

### fileExists(path: string): Promise<boolean>

检查文件是否存在

**参数：**
- `path`: 文件路径

**返回：** `Promise<boolean>` - 文件是否存在

**示例：**
```typescript
const exists = await fileExists('/config.json')
if (exists) {
  console.log('文件存在')
}
```

---

### localStorage 对象

浏览器本地存储的封装（支持 JSON 自动序列化）

#### localStorage.setJson<T>(key: string, data: T): void

写入数据到本地存储

**示例：**
```typescript
localStorage.setJson('userSettings', {
  theme: 'dark',
  language: 'zh-CN'
})
```

#### localStorage.getJson<T>(key: string, defaultValue?: T): T | null

从本地存储读取数据

**示例：**
```typescript
const settings = localStorage.getJson('userSettings', { theme: 'light' })
```

#### localStorage.remove(key: string): void

删除指定键

**示例：**
```typescript
localStorage.remove('userSettings')
```

#### localStorage.clear(): void

清空所有本地存储

**示例：**
```typescript
localStorage.clear()
```

---

### downloadJson<T>(data: T, filename?: string): void

下载 JSON 文件到本地

**参数：**
- `data`: 要下载的数据
- `filename`: 文件名（默认: `data.json`）

**示例：**
```typescript
downloadJson({ name: 'test', value: 123 }, 'export.json')
```

---

### uploadJson<T>(): Promise<T>

从用户选择的文件中读取 JSON

**返回：** `Promise<T>` - 解析后的 JSON 对象

**示例：**
```typescript
try {
  const data = await uploadJson()
  console.log('用户上传的数据:', data)
} catch (error) {
  console.error('用户取消或文件格式错误')
}
```

---

## 💡 完整使用示例

### 在 Vue 组件中使用

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { readJson, localStorage, downloadJson, uploadJson } from '@/utils/common'

interface UserConfig {
  theme: string
  language: string
}

const config = ref<UserConfig | null>(null)

onMounted(async () => {
  // 1. 从本地存储读取配置
  let savedConfig = localStorage.getJson<UserConfig>('userConfig')
  
  // 2. 如果没有，从服务器读取
  if (!savedConfig) {
    savedConfig = await readJson<UserConfig>('/config.json')
    localStorage.setJson('userConfig', savedConfig)
  }
  
  config.value = savedConfig
})

// 导出配置
function handleExport() {
  if (config.value) {
    downloadJson(config.value, 'user-config.json')
  }
}

// 导入配置
async function handleImport() {
  try {
    const imported = await uploadJson<UserConfig>()
    config.value = imported
    localStorage.setJson('userConfig', imported)
  } catch (error) {
    console.error('导入失败', error)
  }
}
</script>

<template>
  <div>
    <h1>当前配置</h1>
    <pre>{{ config }}</pre>
    <button @click="handleExport">导出配置</button>
    <button @click="handleImport">导入配置</button>
  </div>
</template>
```

---

## ⚠️ 注意事项

1. **读取文件路径**：
   - `/config.json` - 从 `public` 目录读取
   - `http://...` - 从远程服务器读取

2. **跨域问题**：
   - 远程 URL 需要服务器支持 CORS

3. **浏览器限制**：
   - 无法直接写入本地文件系统
   - 写入操作需要通过后端 API 或使用 `localStorage`

4. **文件大小**：
   - `localStorage` 限制约 5-10MB
   - 大文件建议使用后端 API

---

## 🔧 TypeScript 类型支持

所有函数都支持泛型，可以指定返回类型：

```typescript
interface User {
  id: number
  name: string
}

const user = await readJson<User>('/user.json')
// user 的类型是 User

const users = await readJson<User[]>('/users.json')
// users 的类型是 User[]
```
