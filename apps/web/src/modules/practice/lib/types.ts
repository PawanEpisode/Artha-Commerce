import { z } from 'zod'

export type SessionMode = 'untimed' | 'timed' | 'chapter_quiz' | 'revision' | 'custom_test' | 'exam'
export type SessionStatus = 'created' | 'in_progress' | 'paused' | 'submitted' | 'auto_submitted' | 'abandoned'
export type FeedbackPolicy = 'instant' | 'after_section' | 'at_end' | 'never_until_submit'
export type ScoringProfile = 'practice' | 'official'
export type AnswerResult = 'correct' | 'incorrect' | 'skipped' | 'partial'
export type MistakeReason = 'concept' | 'silly' | 'calculation' | 'time' | 'not_read' | 'forgot' | 'guess' | 'other'

export interface SessionPlayableOption {
  id: string
  body_md: string
  pinned: boolean
}

export interface SessionItemView {
  position: number
  question_id: string
  kind: string
  stem_md: string
  options: SessionPlayableOption[]
  marks_max: number | string
  negative_max: number | string
  status: string
  selected_option_ids: string[]
  numeric_value: number | null
  numeric_unit: string | null
  time_spent_ms: number
  marked_for_review: boolean
  doubt: boolean
  confidence: number | null
  result?: AnswerResult | null
  marks_awarded?: number | string | null
  negative_applied?: number | string
  explanation_md?: string | null
  feedback?: string | null
}

export interface SessionView {
  id: string
  mode: SessionMode
  title: string
  status: SessionStatus
  feedback_policy: FeedbackPolicy
  scoring_profile: ScoringProfile
  question_count: number
  total_marks: number | string
  time_limit_seconds: number | null
  started_at: string | null
  deadline_at: string | null
  paused_at: string | null
  paused_total_seconds: number
  /** The server's time when this was sent; the clock reads time from it, not from the device. */
  server_now: string
  /** False for exams and timed past papers: the clock does not stop. */
  allow_pause: boolean
  score: number | string | null
  max_score: number | string | null
  score_status: string
  items: SessionItemView[]
}

/** The few fields a clock needs about a session (what `start/` and `active/` answer). */
export interface SessionClockView {
  id: string
  title: string
  mode: SessionMode
  status: SessionStatus
  question_count: number
  time_limit_seconds: number | null
  started_at: string | null
  deadline_at: string | null
  paused_at: string | null
  paused_total_seconds: number
  server_now: string
}

export interface SessionRow {
  id: string
  mode: SessionMode
  title: string
  status: SessionStatus
  question_count: number
  score: number | string | null
  max_score: number | string | null
  score_status: string
  submitted_at: string | null
  created_at: string
}

export interface ChapterProgress {
  attempted: number
  correct_last: number
  wrong_last: number
  bookmarked: number
  due: number
  avg_time_ms: number
  last_attempt_at: string | null
}

export interface MistakeRow {
  question_id: string
  mistake_reason: MistakeReason | null
  created_at: string
}

export interface BookmarkRow {
  question_id: string
  bookmarked_at: string
  notes?: string
}

export interface CreateSessionParams {
  origin?: string
  mode?: SessionMode
  title?: string
  picker?: string
  picker_params?: Record<string, unknown>
  feedback_policy?: FeedbackPolicy
  config?: Record<string, unknown>
  client_id?: string
}

export interface AnswerSavePayload {
  selected_option_ids?: string[]
  numeric_value?: number | null
  client_ts?: string
  time_spent_ms?: number
  confidence?: number | null
  flagged?: boolean
  notes_md?: string
}

export const practiceBuilderSearchSchema = z.object({
  subject: z.string().optional().catch(undefined),
  chapter: z.string().optional().catch(undefined),
  mode: z.string().optional().catch(undefined),
  kind: z.string().optional().catch(undefined),
  n: z.coerce.number().optional().catch(undefined),
})
export type PracticeBuilderSearch = z.infer<typeof practiceBuilderSearchSchema>

export const practicePlayerSearchSchema = z.object({
  q: z.coerce.number().optional().catch(undefined),
})
export type PracticePlayerSearch = z.infer<typeof practicePlayerSearchSchema>
