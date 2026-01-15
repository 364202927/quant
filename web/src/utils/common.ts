/**
 * 读取 JSON 文件
 * @param path 文件路径（相对于 public 目录或绝对 URL）
 * @returns Promise<T> 解析后的 JSON 对象
 */
export async function readJson<T = any>(path: string): Promise<T> {
    try {
        const response = await fetch(path)
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
        }
        const data = await response.json()
        return data
    } catch (error) {
        console.error(`读取 JSON 文件失败: ${path}`, error)
        throw error
    }
}

/**
 * 写入 JSON 文件（通过后端 API）
 * @param path API 路径
 * @param data 要写入的数据
 * @returns Promise<boolean> 是否成功
 */
export async function writeJson<T = any>(path: string, data: T): Promise<boolean> {
    try {
        const response = await fetch(path, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
        }

        return true
    } catch (error) {
        console.error(`写入 JSON 文件失败: ${path}`, error)
        throw error
    }
}

/**
 * 检查文件是否存在（通过 HEAD 请求）
 * @param path 文件路径
 * @returns Promise<boolean> 文件是否存在
 */
export async function fileExists(path: string): Promise<boolean> {
    try {
        const response = await fetch(path, { method: 'HEAD' })
        return response.ok
    } catch (error) {
        console.error(`检查文件存在性失败: ${path}`, error)
        return false
    }
}

/**
 * 本地存储操作封装
 */
export const localStorage = {
    /**
     * 写入本地存储（JSON 格式）
     */
    setJson<T = any>(key: string, data: T): void {
        try {
            window.localStorage.setItem(key, JSON.stringify(data))
        } catch (error) {
            console.error(`写入 localStorage 失败: ${key}`, error)
            throw error
        }
    },

    /**
     * 读取本地存储（JSON 格式）
     */
    getJson<T = any>(key: string, defaultValue?: T): T | null {
        try {
            const item = window.localStorage.getItem(key)
            if (!item) return defaultValue || null
            return JSON.parse(item) as T
        } catch (error) {
            console.error(`读取 localStorage 失败: ${key}`, error)
            return defaultValue || null
        }
    },

    /**
     * 删除本地存储
     */
    remove(key: string): void {
        window.localStorage.removeItem(key)
    },

    /**
     * 清空本地存储
     */
    clear(): void {
        window.localStorage.clear()
    }
}

/**
 * 下载 JSON 文件到本地
 * @param data 要下载的数据
 * @param filename 文件名
 */
export function downloadJson<T = any>(data: T, filename: string = 'data.json'): void {
    try {
        const json = JSON.stringify(data, null, 2)
        const blob = new Blob([json], { type: 'application/json' })
        const url = URL.createObjectURL(blob)

        const link = document.createElement('a')
        link.href = url
        link.download = filename
        document.body.appendChild(link)
        link.click()

        document.body.removeChild(link)
        URL.revokeObjectURL(url)
    } catch (error) {
        console.error('下载 JSON 文件失败:', error)
        throw error
    }
}

/**
 * 从用户选择的文件中读取 JSON
 * @returns Promise<T> 解析后的 JSON 对象
 */
export function uploadJson<T = any>(): Promise<T> {
    return new Promise((resolve, reject) => {
        const input = document.createElement('input')
        input.type = 'file'
        input.accept = '.json,application/json'

        input.onchange = async (e: Event) => {
            const target = e.target as HTMLInputElement
            const file = target.files?.[0]

            if (!file) {
                reject(new Error('未选择文件'))
                return
            }

            try {
                const text = await file.text()
                const data = JSON.parse(text) as T
                resolve(data)
            } catch (error) {
                reject(error)
            }
        }

        input.click()
    })
}

/**
 * API 配置
 */
const API_CONFIG = {
    baseURL: 'http://localhost:8000',
    timeout: 5000
}

/**
 * 统一的 API 响应接口
 */
export interface ApiResponse<T = any> {
    code?: number
    message?: string
    data?: T
    [key: string]: any
}

/**
 * 发送 GET 消息到后端
 * @param id 消息 ID
 * @param args 其他参数，会被转换为查询字符串
 */
export async function sendMessage(id: number, ...args: any[]): Promise<ApiResponse> {
    const params = new URLSearchParams()
    params.append('id', String(id))
    // 将其他参数序列化为查询字符串
    args.forEach((arg, index) => {
        params.append(`arg${index}`, typeof arg === 'object' ? JSON.stringify(arg) : String(arg))
    })
    return apiRequest('GET', `/api/getMessage?${params.toString()}`)
}

/**
 * 发送 POST 消息到后端
 * @param id 消息 ID
 * @param args 消息内容（会被包装成对象发送）
 */
export async function postMessage(id: number, ...args: any[]): Promise<ApiResponse> {
    const payload = {
        id: id,
        args: args
    }
    return apiRequest('POST', '/api/postMessage', payload)
}

/**
 * 通用的 API 请求方法
 * @param method HTTP 方法
 * @param endpoint API 端点
 * @param data 请求数据
 * @returns Promise<ApiResponse> 后端响应
 */
export async function apiRequest<T = any>(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    endpoint: string,
    data?: any
): Promise<ApiResponse<T>> {
    try {
        const url = `${API_CONFIG.baseURL}${endpoint}`
        const options: RequestInit = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
            signal: AbortSignal.timeout(API_CONFIG.timeout)
        }

        if (data && method !== 'GET')
            options.body = JSON.stringify(data)

        const response = await fetch(url, options)
        if (!response.ok)
            throw new Error(`HTTP error! status: ${response.status}`)

        const responseData = await response.json()
        return responseData
    } catch (error) {
        console.error(`API 请求失败: ${method} ${endpoint}`, error)
        throw error
    }
}