import { api, publicApi } from '~/lib/api'

import type {
  FixSetResponse,
  GoalItem,
  GroupByOption,
  MistakesData,
  OverviewData,
  PerformanceData,
  PublicShareData,
  RangeWindow,
  ReadinessData,
  ReportItem,
  SettingsData,
  ShareResponse,
  SpeedData,
  TrendsData,
  WeakTopicsData,
} from './types'

export const analyticsApi = {
  getOverview: async (range: RangeWindow = '30d'): Promise<OverviewData> => {
    return await api<OverviewData>(`/analytics/overview/?range=${range}`)
  },

  getPerformance: async (by: GroupByOption = 'chapter', range: RangeWindow = '30d'): Promise<PerformanceData> => {
    return await api<PerformanceData>(`/analytics/performance/?by=${by}&range=${range}`)
  },

  getTrends: async (window: RangeWindow = '30d'): Promise<TrendsData> => {
    return await api<TrendsData>(`/analytics/trends/?window=${window}`)
  },

  getWeakTopics: async (limit: number = 8): Promise<WeakTopicsData> => {
    return await api<WeakTopicsData>(`/analytics/weak-topics/?limit=${limit}`)
  },

  getSpeed: async (range: RangeWindow = '30d'): Promise<SpeedData> => {
    return await api<SpeedData>(`/analytics/speed/?range=${range}`)
  },

  getMistakes: async (range: RangeWindow = '30d'): Promise<MistakesData> => {
    return await api<MistakesData>(`/analytics/mistakes/?range=${range}`)
  },

  getReadiness: async (): Promise<ReadinessData> => {
    return await api<ReadinessData>('/analytics/readiness/')
  },

  buildFixSet: async (payload: { topic_id?: string; chapter_id?: string; limit?: number }): Promise<FixSetResponse> => {
    return await api<FixSetResponse>('/analytics/fix-sets/', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  refreshAnalytics: async (limit: number = 50): Promise<{ refreshed_sessions: number }> => {
    return await api<{ refreshed_sessions: number }>('/analytics/refresh/', {
      method: 'POST',
      body: JSON.stringify({ limit }),
    })
  },

  getSettings: async (): Promise<SettingsData> => {
    return await api<SettingsData>('/analytics/settings/')
  },

  updateSettings: async (payload: Partial<SettingsData>): Promise<SettingsData> => {
    return await api<SettingsData>('/analytics/settings/', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  listGoals: async (): Promise<{ items: GoalItem[] }> => {
    return await api<{ items: GoalItem[] }>('/analytics/goals/')
  },

  createGoal: async (payload: { target_kind: string; target_value: string }): Promise<GoalItem> => {
    return await api<GoalItem>('/analytics/goals/', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  listReports: async (): Promise<{ items: ReportItem[] }> => {
    return await api<{ items: ReportItem[] }>('/analytics/reports/')
  },

  createReport: async (payload: {
    period_kind: string
    include_name?: boolean
    include_mistakes?: boolean
    include_time?: boolean
  }): Promise<{ id: string; status: string }> => {
    return await api<{ id: string; status: string }>('/analytics/reports/', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  createShare: async (payload: { report_id: string; scopes?: string[] }): Promise<ShareResponse> => {
    return await api<ShareResponse>('/analytics/shares/', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getPublicShare: async (token: string): Promise<PublicShareData | null> => {
    return await publicApi<PublicShareData>(`/analytics/shares/${token}/`)
  },
}
