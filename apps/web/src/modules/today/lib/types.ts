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
  planned_minutes: number
  counts: Counts
  starter_task_id: string | null
  backlog: Backlog[]
  tiles: Tile[]
  tasks: Task[]
  streak: { current: number; best?: number } | null
  goal: { target_minutes: number; done_seconds: number; percent: number } | null
  celebrate: boolean
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
