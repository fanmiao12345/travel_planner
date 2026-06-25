export type Locale = 'en' | 'zh'

export interface Translations {
  app: { title: string; subtitle: string }
  nav: { chat: string; eval: string; skills: string }
  chat: {
    placeholder: string
    send: string
    planning: string
    awaitingReview: string
    confirm: string
    modify: string
    restart: string
    modificationHint: string
    noMessages: string
    welcome: string
  }
  agents: {
    route_planner: string
    weather_forecaster: string
    transport_advisor: string
    accommodation_manager: string
    food_advisor: string
    budget_optimizer: string
    supervisor: string
    summarize: string
  }
  result: {
    overview: string
    weather: string
    transport: string
    accommodation: string
    food: string
    budget: string
    sources: string
  }
  eval: {
    title: string
    accuracy: string
    latency: string
    tokens: string
    toolSuccessRate: string
    noData: string
  }
  skills: {
    title: string
    enabled: string
    disabled: string
    dependencies: string
    version: string
  }
  error: {
    title: string
    retry: string
  }
}

export const translations: Record<Locale, Translations> = {
  zh: {
    app: { title: '出游计划', subtitle: '多智能体旅行规划平台' },
    nav: { chat: '旅行规划', eval: '评估仪表盘', skills: 'Skill 管理' },
    chat: {
      placeholder: '描述你的旅行需求，例如：下周从北京去成都，3天，预算5000，2人...',
      send: '发送',
      planning: '正在规划中...',
      awaitingReview: '方案已生成，请审核',
      confirm: '✅ 确认方案',
      modify: '✏️ 修改意见',
      restart: '🔄 重新规划',
      modificationHint: '请输入你的修改意见...',
      noMessages: '还没有消息',
      welcome: '你好！告诉我你的旅行需求，我来帮你规划。',
    },
    agents: {
      route_planner: '路线规划',
      weather_forecaster: '天气查询',
      transport_advisor: '交通方案',
      accommodation_manager: '住宿推荐',
      food_advisor: '美食推荐',
      budget_optimizer: '预算优化',
      supervisor: '调度中心',
      summarize: '方案汇总',
    },
    result: {
      overview: '总览',
      weather: '天气',
      transport: '交通',
      accommodation: '住宿',
      food: '美食',
      budget: '预算',
      sources: '来源',
    },
    eval: {
      title: '评估仪表盘',
      accuracy: '准确率',
      latency: '延迟',
      tokens: 'Token 用量',
      toolSuccessRate: '工具成功率',
      noData: '暂无评估数据',
    },
    skills: {
      title: 'Skill 管理',
      enabled: '已启用',
      disabled: '已禁用',
      dependencies: '依赖',
      version: '版本',
    },
    error: { title: '出错了', retry: '重试' },
  },
  en: {
    app: { title: 'Travel Planner', subtitle: 'Multi-Agent Travel Planning Platform' },
    nav: { chat: 'Plan Trip', eval: 'Evaluation', skills: 'Skills' },
    chat: {
      placeholder: 'Describe your trip, e.g.: Beijing to Chengdu next week, 3 days, budget 5000, 2 people...',
      send: 'Send',
      planning: 'Planning...',
      awaitingReview: 'Plan ready for review',
      confirm: '✅ Confirm',
      modify: '✏️ Modify',
      restart: '🔄 Restart',
      modificationHint: 'Enter your modification feedback...',
      noMessages: 'No messages yet',
      welcome: 'Hi! Tell me about your trip and I\'ll help you plan it.',
    },
    agents: {
      route_planner: 'Route Planner',
      weather_forecaster: 'Weather',
      transport_advisor: 'Transport',
      accommodation_manager: 'Accommodation',
      food_advisor: 'Food',
      budget_optimizer: 'Budget',
      supervisor: 'Supervisor',
      summarize: 'Summary',
    },
    result: {
      overview: 'Overview',
      weather: 'Weather',
      transport: 'Transport',
      accommodation: 'Stay',
      food: 'Food',
      budget: 'Budget',
      sources: 'Sources',
    },
    eval: {
      title: 'Evaluation Dashboard',
      accuracy: 'Accuracy',
      latency: 'Latency',
      tokens: 'Tokens',
      toolSuccessRate: 'Tool Success Rate',
      noData: 'No evaluation data yet',
    },
    skills: {
      title: 'Skill Manager',
      enabled: 'Enabled',
      disabled: 'Disabled',
      dependencies: 'Dependencies',
      version: 'Version',
    },
    error: { title: 'Error', retry: 'Retry' },
  },
}
