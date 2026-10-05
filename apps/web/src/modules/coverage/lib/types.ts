/** Shapes returned by the coverage API (`/api/v1/coverage/...`). Mirrors apps/api/modules/coverage/serializers.py. */

import type { ElectiveSlotInfo } from '~/modules/syllabus'

export type ChapterStatus =
  'not_started' | 'reading' | 'practised' | 'revised_once' | 'revised_twice_plus' | 'exam_ready'

export type Confidence = 'red' | 'amber' | 'green'

export interface Rollup {
  pct_simple: number
  pct_weighted: number
  chapters_total: number
  chapters_done: number
}

export interface Enrollment {
  id: string
  status: 'active' | 'archived'
  course: { code: string; name: string }
  level: { id: string; code: string; name: string }
  scheme: { id: string; code: string; name: string }
  target_term: { id: string; code: string; name: string } | null
  exam_date: string | null
  days_remaining: number | null
  daily_hours: number | null
  carried_from: string | null
  /** Elective papers the student has not chosen yet. */
  electives_pending: number
  created_at: string | null
}

export interface SubjectRow extends Rollup {
  id: string
  key: string
  name: string
  paper_number: number | null
  total_marks: number | null
  group_key: string | null
  /** Key of the elective slot this paper is an option of, or null for a core paper. */
  elective_slot: string | null
  excluded_chapters: number
}

/** An elective slot with the student's choice (a subject id), or null while they have not chosen. */
export interface ElectiveSlot extends ElectiveSlotInfo {
  chosen: string | null
}

export interface GroupRow extends Rollup {
  id: string
  key: string
  name: string
}

export interface Overview {
  enrollment: Enrollment
  weighted_default: boolean
  level: Rollup
  groups: GroupRow[]
  subjects: SubjectRow[]
  electives: ElectiveSlot[]
  due_count: number
}

export interface ChapterRow {
  id: string
  key: string
  name: string
  section: string
  marks_min: number | null
  marks_max: number | null
  marks_weight: number
  has_topics: boolean
  topics_total: number
  topics_done: number
  coverage_pct: number
  status: ChapterStatus
  confidence: Confidence | null
  is_excluded: boolean
  components: { read: number; practice: number; revise: number; mock: number }
  practice_count: number
  mock_count: number
  revision_count: number
  targets: { practice: number; revisions: number; mocks: number }
  total_study_seconds: number
  last_studied_at: string | null
  last_revised_at: string | null
  next_revision_due: string | null
}

export interface SubjectCoverage {
  subject: Omit<SubjectRow, 'excluded_chapters'>
  chapters: ChapterRow[]
}

export interface TopicRow {
  id: string
  key: string
  name: string
  kind: string
  is_done: boolean
}

export interface CoverageEventRow {
  id: string
  type: string
  value: number | null
  source: string
  occurred_at: string | null
}

export interface ChapterCoverage {
  chapter: ChapterRow
  subject: { id: string; key: string; name: string }
  prev_chapter: { id: string; name: string } | null
  next_chapter: { id: string; name: string } | null
  topics: TopicRow[]
  events: CoverageEventRow[]
  revision_history: CoverageEventRow[]
}

/** Returned by every chapter write, so one response refreshes the chapter and the roll-ups above it. */
export interface ChapterState {
  chapter: ChapterRow
  subject: Rollup
  level: Rollup
}

export interface DueRow extends ChapterRow {
  subject: { id: string; key: string; name: string }
  overdue_days: number
}

export interface Due {
  today: string
  results: DueRow[]
}

export interface CoverageSettings {
  w_read: number
  w_practice: number
  w_revise: number
  w_mock: number
  revision_days: number[]
  weighted_default: boolean
}

export interface CatchupResult {
  overview: Overview
  [key: string]: unknown
}

export type EventType = 'practice_done' | 'mock_done' | 'revision_done'

export interface SwitchChapterRef {
  id: string
  key: string
  name: string
  subject: { id: string; key: string; name: string }
}

export interface SwitchCarried extends SwitchChapterRef {
  /** same, split or merged: how the old chapter(s) map onto this one. */
  relation: string
  from: SwitchChapterRef[]
}

export interface SwitchSummary {
  carried_chapters: number
  new_chapters: number
  removed_chapters: number
  carried: SwitchCarried[]
  new: SwitchChapterRef[]
  removed: SwitchChapterRef[]
}

export interface ElectivesResult {
  electives: ElectiveSlot[]
  overview: Overview
}

export type EnrollmentWithSummary = Enrollment & { switch_summary?: SwitchSummary }
