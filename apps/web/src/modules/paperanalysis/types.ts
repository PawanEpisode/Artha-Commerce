export type DataStatus = 'ready' | 'limited' | 'insufficient' | 'withheld'
export type ConfidenceTier = 'high' | 'medium' | 'low' | 'insufficient'
export type ParetoTier = 'core' | 'next' | 'rest'
export type PlanItemState = 'planned' | 'done' | 'skipped' | 'moved'
export type PlanMode = 'full' | 'key_points'

export interface SubjectStatus {
  subject_key: string
  subject_name?: string
  data_status: DataStatus
  papers_published: number
  papers_target: number
  days_left: number | null
  seo_indexable: boolean
  withheld_reason?: string | null
}

export interface ChapterStatsRow {
  chapter_id: string
  chapter_key: string
  name: string
  section: string
  papers_considered: number
  asked_n: number
  avg_effective: number
  avg_when_asked: number | null
  max_effective: number | null
  last_asked_term_code: string | null
  share_of_marks: number | null
  trend: number | null
  comparability: string
  carried_papers: number
  weight_basis: string
}

export interface PatternsResponse {
  papers_considered: number
  avg_total_marks: number
  avg_attemptable_marks: number
  avg_optional_marks: number
  formats: Record<string, number>
}

export interface ChapterHistorySitting {
  term_code: string
  paper_title: string
  paper_kind: string
  marks_offered: number
  marks_effective: number
  marks_compulsory: number
  question_count: number
  marks_theory: number
  marks_practical: number
  marks_objective: number
  marks_descriptive: number
}

export interface ReasonPayload {
  code: string
  params: Record<string, unknown>
  sentence: string
}

export interface ScoredChapter {
  chapter_id: string
  chapter_key: string
  name: string
  rank: number
  score: number
  tier: ParetoTier
  confidence: ConfidenceTier
  components: {
    H: number
    F: number
    T: number
    W: number
    G: number
  }
  expected_marks: number
  weight_basis: string
  comparability: string
  history?: Record<string, unknown>
  student?: {
    coverage_pct?: number
    answered?: number
    accuracy?: number
  }
  reasons: ReasonPayload[]
  caveats: string[]
  links?: Record<string, string>
}

export interface SubjectPriority {
  subject_key: string
  data_status: DataStatus
  ranking: 'available' | 'withheld'
  papers_considered: number
  sources: {
    exam: number
    mtp: number
    rtp: number
  }
  confidence: ConfidenceTier
  core_share_of_marks: number
  tiers: {
    core: number
    next: number
    rest: number
  }
  chapters: ScoredChapter[]
}

export interface PriorityView {
  v: number
  snapshot_id: string
  engine_version: string
  weightset_id: string
  template_version: number
  generated_at: string
  days_left: number
  exam_date_source: string
  disclaimer_key: string
  subjects: SubjectPriority[]
}

export interface PlanItem {
  id: string
  chapter_id: string
  subject_key: string
  chapter_key: string
  planned_date: string
  position: number
  minutes: number
  mode: PlanMode
  expected_gain: number
  mph: number
  state: PlanItemState
  completed_at?: string | null
}

export interface Plan {
  id: string
  client_id: string
  status: 'active' | 'superseded' | 'ended'
  days: number
  hours_per_day: number
  start_date: string
  end_date: string
  subject_keys: string[]
  balance_subjects: boolean
  summary: {
    budget_hours: number
    hours_used: number
    covered_share: number
    items_count: number
  }
  items: PlanItem[]
}

export interface PlanPreviewItem {
  chapter_id: string
  subject_key: string
  chapter_key: string
  name: string
  minutes: number
  mode: PlanMode
  expected_gain: number
  mph: number
  effort_basis: string
}

export interface PlanPreview {
  budget_hours: number
  hours_used: number
  covered_share: number
  items: PlanPreviewItem[]
  left_out: {
    chapters_n: number
    share: number
  }
  warnings: string[]
}

export interface PaperAnalysisSettings {
  window: number
  include_practice: boolean
  include_older: boolean
  confidence_mode: string
}

export interface AskedSummaryBadge {
  scope: 'question' | 'topic' | 'chapter'
  asked_n: number
  window_n: number
  last_asked_term_code: string | null
  last_asked_year: number | null
  label_key: string
  label: string
}

export interface EditorialAllocation {
  id: string
  chapter_id: string
  chapter_key: string
  chapter_name: string
  marks: string
  share: string
  status: 'suggested' | 'confirmed' | 'rejected' | 'disputed'
  origin: string
  basis: string
  confidence?: number | null
  rationale?: string | null
}

export interface EditorialQuestion {
  id: string
  label: string
  position: number
  marks: string
  format: string
  nature?: string | null
  section_label: string
  alloc_state: 'untagged' | 'suggested' | 'confirmed' | 'disputed'
  qa_state: 'pending' | 'accepted' | 'rejected' | 'escalated'
  rev: number
  allocations: EditorialAllocation[]
}

export interface EditorialPaperDetail {
  id: string
  title: string
  subject_id: string
  subject_key: string
  scheme_id: string
  term_code: string
  paper_kind: string
  total_marks: string
  confirmed_marks: string
  status: 'draft' | 'in_review' | 'published' | 'retracted'
  question_count: number
  rev: number
  questions: EditorialQuestion[]
}
