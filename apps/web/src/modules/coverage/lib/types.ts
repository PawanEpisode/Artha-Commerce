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
  /** Chapters with any progress, finished ones included. The ring is an average of partial chapters. */
  chapters_started: number
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
  /** Planned study time per day in whole minutes (15 to 960), or null when not set. */
  daily_minutes: number | null
  /** @deprecated Decimal hours mirror of `daily_minutes`, kept for one release. Read `daily_minutes`. */
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
  /** Server-side view of the same numbers, clamped. The screens derive it with `chapterActivities` (lib/rules.ts). */
  activities?: Record<
    'practice' | 'revisions' | 'mocks',
    { done: number; target: number; logged: number; can_log: boolean }
  >
  confidence_gate?: { unlocked: boolean; required_pct: number; current_pct: number }
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

/** What the student wants to finish in every chapter. 0 means "not tracked". Mirrors the API's `targets`. */
export interface Targets {
  practice_sets: number
  revisions: number
  mocks: number
}

export type PresetKey = 'light' | 'standard' | 'intense'
export type TargetsPreset = PresetKey | 'custom'

export interface TargetPreset extends Targets {
  key: PresetKey
  label: string
}

/** How many chapter percentages a change of targets moves. */
export interface TargetsImpact {
  chapters_changed: number
  chapters_dropping: number
  chapters_rising: number
}

/** The weights and revision gaps: saved together, independent of the targets. */
export interface WeightSettings {
  w_read: number
  w_practice: number
  w_revise: number
  w_mock: number
  revision_days: number[]
  weighted_default: boolean
}

export interface CoverageSettings extends WeightSettings {
  targets: Targets
  targets_preset: TargetsPreset
  /** Bumps on every change of targets. */
  targets_version: number
  /** False until the student has chosen their targets once (onboarding or settings). */
  targets_confirmed: boolean
  target_presets: TargetPreset[]
  target_limits: { min: number; max: number }
}

export type SettingsSaved = CoverageSettings & { impact?: TargetsImpact }

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
