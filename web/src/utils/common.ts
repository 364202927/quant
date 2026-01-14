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
