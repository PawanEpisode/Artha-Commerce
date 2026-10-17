/**
 * Performance Analytics types (F-10 R1, R2, R3).
 */

export type RangeWindow = '7d' | '30d' | '90d' | 'all'

export type GroupByOption = 'chapter' | 'topic' | 'difficulty' | 'kind' | 'source'

export interface OverviewData {
  total_answered: number
  total_correct: number
  overall_accuracy: number
  overall_accuracy_pct: number
  study_seconds: number
  study_hours_formatted: string
  coverage_percentage: number
  days_active: number
  facts_version: number
  last_calculated_at: string
}

export interface PerformanceItem {
  key: string
  label: string
  chapter_id?: string
  chapter_name?: string
  group_key?: string
  group_name?: string
  answered: number
  correct: number
  accuracy?: number
  accuracy_pct: number
  shrunk_accuracy_pct: number
  wilson_low_pct: number
  wilson_high_pct: number
  study_seconds: number
  avg_pace_ratio: number | null
}

export interface PerformanceData {
  group_by: GroupByOption
  range: RangeWindow
  items: PerformanceItem[]
}

export interface TrendItem {
  date: string
  answered: number
  correct: number
  accuracy_pct: number
  moving_avg_accuracy_pct: number
}

export interface TrendsData {
  window: RangeWindow
  items: TrendItem[]
}

export interface WeakTopicItem {
  topic_id: string
  topic_name: string
  chapter_id: string
  chapter_name: string
  subject_key: string
  answered: number
  correct: number
  accuracy?: number
  accuracy_pct: number
  shrunk_accuracy_pct: number
  mistakes_count: number
}

export interface WeakTopicsData {
  items: WeakTopicItem[]
}

export type SpeedQuadrantKey = 'fast_and_wrong' | 'slow_and_right' | 'on_target' | 'slow_and_wrong'

export interface SpeedData {
  timed_answers_count: number
  overall_pace_ratio: number | null
  quadrants: {
    fast_and_wrong: { count: number; pct: number }
    slow_and_right: { count: number; pct: number }
    on_target: { count: number; pct: number }
    slow_and_wrong: { count: number; pct: number }
  }
}

export interface MistakeItem {
  reason: string
  label: string
  reason_label?: string
  count: number
  percentage: number
  share_pct?: number
}

export interface MistakesData {
  total_tagged_mistakes: number
  items: MistakeItem[]
}

export type ReadinessState = 'none' | 'sparse' | 'early' | 'ready' | 'stale'
export type ConfidenceLevel = 'high' | 'medium' | 'low'

export interface ReadinessComponent {
  key: string
  label: string
  value: number
  weight: number
  points: number
  available: boolean
}

export interface ReadinessLever {
  action: string
  impact_points: number
  target_type: string
  target_id: string | null
  target_name: string | null
}

export interface ReadinessData {
  state: ReadinessState
  score: number | null
  half_width: number | null
  confidence: ConfidenceLevel | null
  label: string | null
  components: ReadinessComponent[]
  levers: ReadinessLever[]
  missing_gates: string[]
}

export interface ReportItem {
  id: string
  status: 'pending' | 'ready' | 'failed'
  period_kind: string
  from_date: string
  to_date: string
  created_at: string
  expires_at: string
  share_token?: string
}

export interface ShareResponse {
  token: string
  public_url: string
  scopes: string[]
  expires_at: string
}

export interface PublicShareData {
  student_name: string | null
  period_kind: string
  from_date: string
  to_date: string
  created_at: string
  overview: OverviewData
  readiness: ReadinessData
}

export interface FixSetResponse {
  session_id: string
  item_count: number
}

export interface SettingsData {
  target_accuracy: string
  target_pace_ratio: string
  decay_half_life_days: number
  time_budget_minutes_per_day: number
}

export interface GoalItem {
  id: string
  target_kind: string
  target_value: string
  effective_from: string
  effective_to: string | null
}
