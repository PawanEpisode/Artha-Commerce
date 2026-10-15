/** Wire types of /api/v1/today/ (docs/F-13-API-CONTRACT.md). */

export type TaskState = 'suggested' | 'accepted' | 'done' | 'skipped' | 'snoozed' | 'expired'
export type TaskOrigin = 'provider' | 'user' | 'planner'
export type Phase = 'steady' | 'build' | 'consolidate' | 'sprint' | 'final' | 'post_exam'
export type PlanState = 'ready' | 'not_enrolled' | 'post_exam'

export interface TaskLink {
  path: string
  search: Record<string, string | number | boolean>
}

export interface TaskProgress {
  done: number
  target: number
}

export interface Task {
  id: string
  origin: TaskOrigin
  kind: string
  slot: string
  title: string
  reason: string
  reason_code: string
  why: { modifiers: unknown[]; signals: Record<string, unknown> }
  est_minutes: number
  progress: TaskProgress | null
  target: number | null
  state: TaskState
  link: TaskLink | null
  subject_id: string | null
  chapter_id: string | null
  manual_action: { label: string; default: boolean } | null
  is_must_do: boolean
  version: number
}

export interface Counts {
  planned: number
  done: number
  open: number
  skipped: number
  snoozed: number
}

export interface Tile {
  subject_id: string | null
  subject_key: string
  name: string
  tasks: string[]
}

export interface Backlog {
  kind: string
  count: number
  scheduled: number
  label: string
  link: TaskLink | null
}

export interface WeekDay {
  date: string
  outcome: string
  planned_count: number
  done_count: number
}

export interface Plan {
  version: number
  date: string
  tz: string
  server_time: string
  state: 'ready'
  phase: Phase
  days_to_exam: number | null
  generation_no: number
  partial: boolean
  failed_providers: string[]
  budget_minutes: number
  budget_source: 'auto' | 'setting' | 'comeback' | 'feedback'
  planned_minutes: number
  counts: Counts
  starter_task_id: string | null
  backlog: Backlog[]
  tiles: Tile[]
  tasks: Task[]
  /** The tracker's streak in days (Today never computes its own). */
  streak: number
  goal: { target_minutes: number; done_seconds: number; percent: number } | null
  celebrate: boolean
  closing: 'celebrate' | 'calm' | null
  tomorrow: unknown
  week?: WeekDay[]
  created?: boolean
}

export interface EmptyPlan {
  version: number
  date: string
  tz: string
  server_time: string
  state: 'not_enrolled' | 'post_exam'
  plan: null
}

export type OpenResult = Plan | EmptyPlan

export const isEmptyPlan = (r: OpenResult): r is EmptyPlan => r.state !== 'ready'

export type ActionName =
  | 'start'
  | 'complete_manual'
  | 'complete_event'
  | 'skip'
  | 'swap'
  | 'snooze'
  | 'undo'
  | 'pin'
  | 'expire'
  | 'restore'
  | 'move'

export type SkipReason = 'not_in_attempt' | 'already_know' | 'no_time' | 'other'
export type SnoozeUntil = 'tomorrow' | 'in_3_days' | 'next_week' | (string & {})
export type UndoFrom = 'done' | 'skipped' | 'deleted'

/** What every task action answers: the task and the plan's counters, so the ring updates without a refetch. */
export interface TaskResponse {
  version: number
  server_time: string
  task: Task
  counts: Counts
  link?: TaskLink
  suppressed_days?: number | null
  undo_until?: string
}

export interface SwapResponse {
  version: number
  server_time: string
  old: Task
  new: Task
  counts: Counts
}

export interface AddTaskBody {
  client_id: string
  title: string
  est_minutes: number
  date?: string
  subject_id?: string | null
  chapter_id?: string | null
}

export interface Preview {
  date: string
  tz: string
  phase: Phase
  days_to_exam: number | null
  count: number
  minutes: number
  tasks: Array<{ kind: string; slot: string; title: string; reason: string; est_minutes: number; subject_key: string }>
  own_tasks: Array<{ id: string; title: string; est_minutes: number; state: TaskState }>
}

export interface TodaySettings {
  minutes_per_day: number | null
  focus_papers: unknown
  disabled_kinds: string[]
  show_tomorrow: boolean
  celebrate: boolean
  lite_mode: 'auto' | 'on' | 'off'
}

export interface EditFields {
  title?: string
  est_minutes?: number
  subject_id?: string | null
  chapter_id?: string | null
  date?: string
}
