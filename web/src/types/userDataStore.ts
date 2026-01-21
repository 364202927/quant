interface notification {
    name: string
    enable: boolean
    type: string
    token: string
    value1: string
    value2: string
}

interface markets {
    name: string
    enable: boolean
    type: string
    apiKey: string
    secret: string
    description: string
    utc: number
}

export class userDataStore {
    private userName: string = ''
    private notifs: notification[] = []
    private exchanges: markets[] = []

    constructor() {

    }

    setUserName(name: string) {
        this.userName = name
    }

}