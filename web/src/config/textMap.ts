/**
 * UI 文本映射配置
 * 集中管理所有界面显示文本，便于统一修改和维护
 */

export const TEXT_MAP = {
  // PageSettings - 账号信息
  settings_account_name_label: '账号名称',
  settings_account_name_placeholder: '请输入账号名称',
  // PageSettings - 通知配置
  settings_notification_empty: '暂无通知配置，点击上方按钮添加',
  // PageSettings - 交易所配置
  settings_exchange_empty: '暂无交易所配置，点击上方按钮添加',
  // PageSettings - AI 配置
  settings_ai_empty: '暂无AI配置，点击上方按钮添加',
  settings_ai_name_placeholder: 'AI名称',
  settings_ai_token_placeholder: 'API Token',
  settings_ai_url_placeholder: 'API URL',
  btn_save: '同步后台',
  prefix_add: '+'



} as const

// 获取文本的辅助函数
export function getText(key: keyof typeof TEXT_MAP): string {
  return TEXT_MAP[key]
}
