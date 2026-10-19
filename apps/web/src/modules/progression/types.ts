export type TransitionType =
  'full_level_pass' | 'group_clearance' | 'exemption_update' | 'scheme_migration' | 'repeat_attempt'

export type StudyMode = 'active_study' | 'weekend_only' | 'work_focus_pause' | 'exam_leave_intensive'

export type PaperStatus = 'passed' | 'exempted' | 'pending' | 'failed'

export interface ActiveEnrollmentSummary {
  id: string
  course_code: string
  course_name: string
  level_code: string
  level_name: string
  scheme_id: string | null
  scheme_name: string
  term_code: string | null
  term_name: string | null
  exam_date: string | null
  daily_minutes: number | null
}

export interface ArticleshipProfileData {
  id?: string
  is_active: boolean
  firm_name: string
  registration_number: string
  training_start_date: string | null
  expected_completion_date: string | null
  study_mode: StudyMode
  weekday_minutes: number
  weekend_minutes: number
  exam_leave_start_date: string | null
  target_groups: string[]
}

export interface ExemptionItem {
  id: string
  subject_key: string
  subject_name: string
  marks_obtained: number
  granted_term_code: string
  valid_until_term_code: string | null
  is_permanent: boolean
  is_exhausted: boolean
  is_valid: boolean
}

export interface AvailableTransition {
  type: TransitionType
  target_level_code?: string
  target_level_name?: string
  label: string
  description: string
}

export interface PaperItem {
  id: string
  key: string
  paper_number?: number | null
  name: string
  total_marks: number
  is_excluded: boolean
}

export interface GroupItem {
  key: string
  name: string
  papers: PaperItem[]
}

export interface ResultPromptState {
  should_prompt: boolean
  term_name: string
  level_name: string
  exam_date?: string | null
}

export interface ProgressionStatus {
  active_enrollment: ActiveEnrollmentSummary | null
  articleship: ArticleshipProfileData
  exemptions: ExemptionItem[]
  available_transitions: AvailableTransition[]
  current_groups: GroupItem[]
  result_prompt: ResultPromptState
}

export interface PaperResultPayload {
  subject_key: string
  status?: PaperStatus
  marks?: number | null
  is_carry_forward?: boolean
  is_permanent?: boolean
}

export interface TransitionPayload {
  transition_type: TransitionType
  trigger?: 'result_prompt' | 'user_initiated' | 'admin'
  target_course_code?: string | null
  target_level_code?: string | null
  target_scheme_id?: string | null
  target_term_id?: string | null
  cleared_group_keys?: string[]
  paper_results?: PaperResultPayload[]
  articleship?: Partial<ArticleshipProfileData> | null
  metadata?: Record<string, unknown>
}

export interface TransitionResult {
  transition_id: string
  status: string
  new_enrollment_id: string
  vault_archived_enrollment_id?: string | null
  message: string
}

export interface RollbackResult {
  transition_id: string
  status: string
  message: string
}

export interface VaultSubject {
  key: string
  paper_number?: number | null
  name: string
}

export interface VaultEnrollment {
  enrollment_id: string
  course_code: string
  course_name: string
  level_code: string
  level_name: string
  scheme_name: string
  term_name: string
  exam_date: string | null
  notes_count: number
  docs_count: number
  subjects: VaultSubject[]
}

export interface TransitionHistoryItem {
  id: string
  transition_type: TransitionType
  trigger: string
  status: string
  effective_date: string
  created_at: string
  can_rollback: boolean
  from_level?: { course_code: string; level_code: string; level_name: string } | null
  to_level?: { course_code: string; level_code: string; level_name: string } | null
  paper_results: Array<{
    subject_key: string
    status: PaperStatus
    marks_obtained?: number | null
    is_carry_forward: boolean
  }>
  metadata: Record<string, unknown>
}
