import type { ActivityType, StudySession } from '~/modules/tracker'

import type { PresetKey } from './presets'

export type Phase = 'focus' | 'short_break' | 'long_break'
export type TimerStatus = 'running' | 'paused' | 'away'
export type EndReason = 'distracted' | 'phone_call' | 'tired' | 'urgent_work' | 'other'

export interface FocusTimer {
  phase: Phase
  status: TimerStatus
  round_number: number
  rounds_before_long: number
  cycle_id: string
  preset: PresetKey
  planned_seconds: number
  elapsed_seconds: number
  remaining_seconds: number
  extension_count: number
  can_extend: boolean
  started_at: string
  paused_at: string | null
  paused_total_seconds: number
  pause_count: number
  ends_at: string | null
  last_seen_at: string
  away_pending: boolean
  auto_start_breaks: boolean
  auto_start_focus: boolean
  subject_id: string | null
  chapter_id: string | null
  activity_type: ActivityType
  client_id: string
  version: number
}

/** What Start will do when nothing runs: the remembered cycle, or round one. */
export interface IdleInfo {
  next_phase: Phase
  next_round: number
  rounds_before_long: number
  cycle_id: string | null
}

export interface FocusSettings {
  preset: PresetKey
  focus_minutes: number
  short_break_minutes: number
  long_break_minutes: number
  rounds_before_long: number
  auto_start_breaks: boolean
  auto_start_focus: boolean
  sound_enabled: boolean
  volume: number
  notifications_enabled: boolean
  intro_seen: boolean
}

export interface FocusState {
  timer: FocusTimer | null
  idle: IdleInfo | null
  live: 'none' | 'stopwatch' | 'pomodoro'
  settings: FocusSettings
  server_time: string
  outcome?: 'saved' | 'too_short' | 'discarded' | 'counted' | 'none'
  session?: StudySession | null
}

export interface SessionPage {
  results: StudySession[]
  next_cursor: string | null
}

export const REASON_OPTIONS: Array<{ value: EndReason; label: string }> = [
  { value: 'distracted', label: 'Got distracted' },
  { value: 'phone_call', label: 'Phone call' },
  { value: 'tired', label: 'Too tired' },
  { value: 'urgent_work', label: 'Urgent work' },
  { value: 'other', label: 'Something else' },
]
