export type PaperKind = 'mtp' | 'mock' | 'generated'
export type SourceTag = 'institute' | 'faculty' | 'editorial' | 'custom'
export type PaperStatus = 'draft' | 'live' | 'archived'
export type RunMode = 'exam' | 'practice'
export type AttemptPhase = 'instructions' | 'reading' | 'writing' | 'upload' | 'done' | 'abandoned'
export type IntegrityClass = 'clean' | 'unverified' | 'suspect' | 'disqualified'
export type PaletteStatus = 'not_visited' | 'not_answered' | 'answered' | 'marked_for_review' | 'marked_answered'

export interface MockPaperCard {
  id: string
  title: string
  kind: PaperKind
  source_tag: SourceTag
  subject_key: string
  subject_name?: string
  total_marks: number
  duration_seconds: number
  reading_seconds: number
  section_timing: 'none' | 'flexible' | 'strict_sequential'
  live_version_id?: string
  attempt_count: number
  status: PaperStatus
  released_at?: string
  answer_key_status: 'hidden' | 'released'
  delivery_mode?: 'native' | 'pdf_companion'
  source_pdf_url?: string
  solution_pdf_url?: string
}

export interface PaperSection {
  id: string
  key: string
  title: string
  position: number
  kind: 'objective' | 'subjective' | 'mixed'
  marks_total: number
  duration_seconds?: number | null
}

export interface PaperChoiceGroup {
  id: string
  key: string
  label: string
  required_count: number
  overflow_policy: 'block' | 'first_n' | 'best_n'
  items: string[]
}

export interface PaperItem {
  id: string
  position: number
  display_label: string
  question_id: string
  marks: number
  negative_marks: number
  section_key: string
  choice_group_key?: string | null
}

export interface PaperDetail extends MockPaperCard {
  description?: string
  instructions_md?: string
  sections: PaperSection[]
  choice_groups: PaperChoiceGroup[]
  items: PaperItem[]
  my_attempt?: {
    id: string
    phase: AttemptPhase
    attempt_no: number
    score?: number | null
    percent?: number | null
  } | null
}

export interface AttemptLayoutItem {
  pos: number
  question_id: string
  section: string
  marks: number
  neg: number
  choice_group?: string | null
  label: string
}

export interface AttemptSectionState {
  key: string
  title: string
  position: number
  status: 'pending' | 'active' | 'closed'
  max_score: number
  time_spent_seconds: number
  closes_at?: string | null
}

export interface AttemptState {
  id: string
  paper_id: string
  paper_title: string
  paper_version_id: string
  run_mode: RunMode
  phase: AttemptPhase
  attempt_no: number
  duration_seconds: number
  reading_seconds: number
  section_timing: 'none' | 'flexible' | 'strict_sequential'
  instructions_accepted_at?: string | null
  reading_ends_at?: string | null
  writing_started_at?: string | null
  writing_ends_at?: string | null
  upload_until?: string | null
  completed_at?: string | null
  lease_epoch: number
  layout: AttemptLayoutItem[]
  sections: AttemptSectionState[]
  instructions_md?: string
  answer_key_status: 'hidden' | 'released'
  delivery_mode?: 'native' | 'pdf_companion'
  source_pdf_url?: string
  solution_pdf_url?: string
}

export interface ClockSyncResponse {
  server_time: string
  phase: AttemptPhase
  remaining_ms: number
  section_remaining_ms: number
  active_section_key: string | null
  auto_submit_due: boolean
}

export interface SectionScore {
  key: string
  title?: string
  score: number
  max_score: number
  answered: number
  correct: number
  incorrect: number
  skipped: number
  not_counted: number
  time_spent_seconds: number
}

export interface AttemptResult {
  attempt_id: string
  paper_title: string
  run_mode: RunMode
  phase: AttemptPhase
  attempt_no: number
  score: number | null
  max_score: number | null
  percent: number | null
  time_used_seconds: number
  integrity_class: IntegrityClass
  percentile_eligible: boolean
  percentile_data?: {
    status: 'computed' | 'pending' | 'unavailable'
    percentile?: number
    band?: string
    cohort_size?: number
  } | null
  sections: SectionScore[]
  choice_resolution?: Record<string, unknown> | null
  completed_at?: string | null
  source_pdf_url?: string
  solution_pdf_url?: string
}

export interface AttemptReviewItem {
  position: number
  question_id: string
  display_label: string
  section_key: string
  kind: string
  stem_html: string
  options?: Array<{ id: string; content_html: string }>
  user_answer?: {
    selected_option_ids?: string[]
    numeric_value?: string | number
  }
  result?: 'correct' | 'incorrect' | 'partial' | 'skipped' | 'ungraded'
  marks_awarded?: number | null
  marks_max: number
  explanation_html?: string
  correct_option_ids?: string[]
  is_excluded_by_choice?: boolean
}

export interface AttemptReview {
  attempt_id: string
  paper_title: string
  score: number | null
  max_score: number | null
  percent: number | null
  items: AttemptReviewItem[]
  source_pdf_url?: string
  solution_pdf_url?: string
}

export interface SeriesCard {
  id: string
  title: string
  slug: string
  kind: string
  description: string
  papers_count: number
  released_at?: string
}

export interface MockTestSettings {
  time_extension_pct: number
  default_run_mode: 'exam' | 'practice'
  focus_reminders: boolean
  keyboard_shortcuts: boolean
  percentile_optin: boolean
  tz?: string
}
