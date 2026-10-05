export type ActivityType = 'reading' | 'practice' | 'revision' | 'notes' | 'mock_test' | 'other'
export type SessionSource = 'pomodoro' | 'stopwatch' | 'manual' | 'auto'

export const ACTIVITY_OPTIONS: ReadonlyArray<{ value: ActivityType; label: string }> = [
  { value: 'reading', label: 'Reading' },
  { value: 'practice', label: 'Practice' },
  { value: 'revision', label: 'Revision' },
  { value: 'notes', label: 'Notes' },
  { value: 'mock_test', label: 'Mock test' },
  { value: 'other', label: 'Other' },
]

export interface Stopwatch {
  status: 'running' | 'paused'
  started_at: string
  paused_at: string | null
  paused_total_seconds: number
  pause_count: number
  elapsed_seconds: number
  last_seen_at: string
  last_active_at: string
  idle_pending: boolean
  idle_prompted_at: string | null
  idle_due: boolean
  subject_id: string | null
  chapter_id: string | null
  activity_type: ActivityType
  client_id: string
  version: number
}

export interface StopwatchState {
  stopwatch: Stopwatch | null
  /** Which other live timer is running ("pomodoro"), if any. */
  live: string | null
  idle_minutes: number
  server_time: string
}

export interface StudySession {
  id: string
  client_id: string | null
  source: SessionSource
  activity_type: ActivityType
  subject_id: string | null
  subject_name: string
  chapter_id: string | null
  chapter_name: string
  status: string
  started_at: string
  ended_at: string
  focus_seconds: number
  paused_total_seconds: number
  pause_count: number
  study_date: string
  tz: string
  is_edited: boolean
  overlaps_other: boolean
  merged_count: number
  idle_trimmed: boolean
  presence_verified: boolean
  split_from_id: string | null
  note?: string
}

export interface StopResult {
  session: StudySession | null
  outcome: string
  server_time: string
}

export interface SessionPage {
  results: StudySession[]
  next_cursor: string | null
}

export interface TrackerSettings {
  idle_minutes: number
  week_start: 0 | 1
  default_activity_type: ActivityType
  tz: string
  auto_capture_enabled: boolean
}

export interface GoalEntry {
  period: 'daily' | 'weekly'
  subject_id: string | null
  target_minutes: number
}

export interface Goal extends GoalEntry {
  id: string
  subject_key: string
  subject_name: string
  effective_from: string
}

export interface GoalProgressEntry {
  period: 'daily' | 'weekly'
  subject_id: string | null
  subject_key: string
  subject_name: string
  target_minutes: number
  done_seconds: number
  percent: number
  remaining_seconds: number
  pace?: { state: 'ahead' | 'on_track' | 'behind'; delta_seconds: number }
}

export interface GoalsPayload {
  goals: Goal[]
  progress: {
    week_start: string
    daily: { target_minutes: number; is_default: boolean; done_seconds: number; percent: number }
    weekly: GoalProgressEntry | null
    subjects: GoalProgressEntry[]
    streak: number
  }
}

export interface SummaryBlock {
  from: string
  to: string
  total_seconds: number
  days_studied: number
  average_seconds_per_studied_day: number
  longest_day: { date: string; seconds: number } | null
  sessions: number
  longest_session_seconds: number
}
export interface Summary extends SummaryBlock {
  previous?: SummaryBlock
  change?: { delta_seconds: number; percent: number | null } | null
}

export type Group = 'day' | 'week' | 'month'
export type SplitBy = 'total' | 'level' | 'group' | 'subject' | 'chapter' | 'activity' | 'source'

export interface SeriesBucket {
  start: string
  end: string
  seconds: number
  parts: Record<string, number>
}
export interface Series {
  from: string
  to: string
  group: Group
  by: SplitBy
  week_start: number
  tz: string
  legend: Array<{ key: string; name: string }>
  buckets: SeriesBucket[]
}

export interface BreakdownItem {
  key: string
  name: string
  seconds: number
  sessions: number
  share_percent: number
  subject_id: string | null
  chapter_id: string | null
}
export interface Breakdown {
  from: string
  to: string
  by: SplitBy
  total_seconds: number
  items: BreakdownItem[]
}

export interface Heatmap {
  from: string
  to: string
  days: Array<{ date: string; seconds: number; level: number }>
}

export interface Hours {
  from: string
  to: string
  tz: string
  approximate: boolean
  hours: number[]
  weekdays: Array<{ weekday: number; seconds: number; days: number }>
}

export interface TimeVsCoverage {
  from: string
  to: string
  subject: { id: string; name: string }
  average_seconds: number
  chapters: Array<{
    chapter_id: string
    key: string
    name: string
    seconds: number
    coverage_percent: number
    flag: string
  }>
}

export interface WeeklySummary {
  week_start: string
  week_end: string
  total_seconds: number
  days_tracked: number
  best_day: { date: string; seconds: number } | null
  top_subject: { name: string; seconds: number } | null
  goal: { target_minutes: number; met: boolean; done_seconds: number } | null
  suggestion:
    | { kind: 'keep_going' }
    | { kind: 'subject_shortfall'; subject_id: string | null; subject_name: string; remaining_seconds: number }
}

export interface ManualInput {
  client_id: string
  started_at: string
  ended_at?: string
  duration_seconds?: number
  subject_id?: string | null
  chapter_id?: string | null
  activity_type?: ActivityType
  note?: string
  on_overlap?: 'trim' | 'keep' | 'reject' | null
  confirm_old?: boolean
}

export interface SessionEdit {
  subject_id?: string | null
  chapter_id?: string | null
  activity_type?: ActivityType
  note?: string
  started_at?: string
  ended_at?: string
  confirm_old?: boolean
}
