import { eMsg } from "."
import { postMessage } from '../utils/common'

export interface userData {
    userName: string
    ccxtRetry: number
    console_e: boolean
    tg_e: boolean
}
export interface newsletter {
    id: string
    token: string
    value1: string
    value2: string
}
export interface ai {
    id: string
    token: string
    url: string
}
export interface markets {
    id: string
    enable: boolean
    exchange: string
    apiKey: string
    secret: string
    description: string
}

export class userDataStore {
    private user: userData
    private notifs: Map<string, newsletter> = new Map()
    private exchanges: Map<string, markets> = new Map()
    private ais: Map<string, ai> = new Map()

    constructor() {
        // 只对userData进行默认初始化
        this.user = {
            userName: 'admin',
            ccxtRetry: 1,
            console_e: false,
            tg_e: false
        }
    }

    // 从服务器初始化数据
    initFromServer(data: { user: userData, apiKey: { market: Record<string, markets>, newsletter: Record<string, newsletter>, ai: Record<string, ai> } }) {
        this.setUser(data.user)
        const dict = {
            ais: data.apiKey.ai,
            notifs: data.apiKey.newsletter,
            exchanges: data.apiKey.market
        }
        for (const [id, data] of Object.entries(dict))
            for (const [key, item] of Object.entries(data))
                this.setApi(id, key, item)
        console.log("~~~~~initFromServer~~~~~~~", this.user, this.notifs, this.exchanges, this.ais)
    }

    // 设置用户数据
    setUser(data: userData) {
        this.user = { ...data }
        if (this.user.userName == '')
            this.user.userName = 'admin'
    }
    // 设置 API 数据（newsletter/markets/ai）
    setApi(key: string, id: string, data: newsletter | markets | ai) {
        const map = this.getMapByKey(key)
        if (map instanceof Map)
            map.set(id, data as any)
    }
    // 删除 API 数据
    deleteApi(key: string, id: string) {
        const map = this.getMapByKey(key)
        if (map instanceof Map)
            map.delete(id)
    }

    // 获取指定类型的 Map
    getMapByKey(key: string): Map<string, newsletter | markets | ai> | userData {
        switch (key) {
            case 'notifs':
                return this.notifs
            case 'exchanges':
                return this.exchanges
            case 'ais':
                return this.ais
            default:
                return this.user
        }
    }

    update2Server() {
        const userData = {
            userName: this.user.userName,
            ccxtRetry: this.user.ccxtRetry,
            external: {
                "console": { "enable": this.user.console_e },
                "tg": { "enable": this.user.tg_e }
            }


        }
        const sendDict = {
            user: userData,
            apiKey: {
                market: this.exchanges,
                newsletter: this.notifs,
                ai: this.ais
            },
            start: [],
        }
        console.log("~~~~~~1~~~~~~~", sendDict)
        // console.log("~~~~~2~~~~~", this.exchanges)
        // console.log("~~~~~3~~~~~", this.notifs)
        // console.log("~~~~~4~~~~~", this.ais)

        postMessage(eMsg.eSaveFile, sendDict)

    }
}