/** Wire types of the planner endpoints (docs/F-13-API-CONTRACT.md, "Planner" and "Feedback, adaptive budget and bonus round"). */

export type Health = 'unknown' | 'on_track' | 'slightly_behind' | 'at_risk'
export type MilestoneKind = 'finish_reading' | 'first_revision' | 'mock' | 'exam_week'
export type MilestoneStatus = 'pending' | 'done' | 'at_risk' | 'missed' | 'dropped'
export type ReplanTrigger = 'missed_days' | 'weekly' | 'manual' | 'exam_date' | 'scheme_switch'
export type OptionName = 'more_time' | 'skim_low_weight' | 'next_attempt'
export type OptionChoice = OptionName | 'none'

export interface Milestone {
  id: string
  kind: MilestoneKind
  subject_key: string
  subject_id: string | null
  subject_name: string | null
  target_date: string
  original_target_date: string
  moved_days: number
  overdue_days: number
  remaining_minutes: number
  status: MilestoneStatus
  done_at: string | null
}

export interface MoreTimeOption {
  option: 'more_time'
  daily_minutes: number
  extra_minutes: number
  feasible: boolean
}

export interface SkimOption {
  option: 'skim_low_weight'
  chapter_count: number
  chapters?: string[]
  saved_minutes: number
  feasible: boolean
}

export interface NextAttemptOption {
  option: 'next_attempt'
  exam_date: string | null
  shortfall_minutes: number | null
  feasible: boolean
}

export type ReplanOption = MoreTimeOption | SkimOption | NextAttemptOption

export interface ReplanMove {
  subject_key: string
  kind: MilestoneKind
  from: string
  to: string
}

export interface ReplanEvent {
  id: string
  trigger: ReplanTrigger
  health_before: Health
  health_after: Health
  shortfall_before: number
  shortfall_after: number
  moved_count: number
  option_chosen: OptionChoice | null
  moved: ReplanMove[]
  options: ReplanOption[]
  created_at: string
}

export interface StudyPlan {
  version: number
  server_time: string
  id: string
  enrollment_id: string
  exam_date: string
  daily_minutes: number
  health: Health
  capacity_minutes: number
  remaining_minutes: number
  shortfall_minutes: number
  reading_deadline: string | null
  revise_until: string | null
  health_checked_at: string | null
  last_replanned_at: string | null
  next_replan_on: string | null
  replan_no: number
  plan_version: number
  tz: string
  milestones: Milestone[]
  pending: ReplanEvent | null
  latest_replan: ReplanEvent | null
}

export type StudyPlanCreated = StudyPlan & { created: boolean }
export type StudyPlanReplanned = StudyPlan & { replan: ReplanEvent | null }

// ---- day feedback, adaptive budget -----------------------------------------------------------------------------------------

export type FeedbackRating = 'too_much' | 'just_right' | 'too_little'

export interface BudgetSuggestion {
  direction: 'too_much' | 'too_little'
  minutes: number
  current: number
}

export interface FeedbackResponse {
  version: number
  server_time: string
  date: string
  rating: FeedbackRating
  suggestion: BudgetSuggestion | null
}

export interface BudgetSuggestionResponse {
  version: number
  server_time: string
  suggestion: BudgetSuggestion | null
}
