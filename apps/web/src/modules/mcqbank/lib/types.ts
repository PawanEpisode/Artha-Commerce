import { z } from 'zod'

export interface SubjectCard {
  code: string
  name: string
  paper_number?: number | null
  total_mcqs: number
}

export interface OpenSession {
  id: string
  title: string
  mode: string
  status: string
  question_count: number
  created_at: string
}

export interface QuickSuggestion {
  chapter_id: string
  subject_key: string
  chapter_key: string
  reasons: string[]
  score: number
  spec: {
    v: number
    subject_key: string
    chapters: Array<{ chapter_id: string; n: number }>
    count: number
    mix: string
  }
}

export interface McqHomeData {
  course: string
  level: string
  subjects: SubjectCard[]
  open_sessions: OpenSession[]
  suggestion: QuickSuggestion | null
}

export interface ChapterTile {
  chapter_id: string
  chapter_key: string
  name: string
  section: string
  available: number
  unseen: number
  wrong_last: number
  bookmarked: number
  due: number
  accuracy_recent: number | null
  last_practised_at: string | null
}

export interface TopicCard {
  id: string
  code: string
  name: string
  count: number
}

export interface ChapterDetailData {
  chapter_id: string
  chapter_key: string
  name: string
  section: string
  topics: TopicCard[]
  difficulty_split: {
    easy: number
    medium: number
    hard: number
  }
  sets: McqSetCard[]
}

export type SetKind = 'platform' | 'icmai_booklet' | 'pyq_section' | 'rtp_mtp' | 'teacher' | 'user'
export type DeliveryMode = 'hosted' | 'link_out'

export interface McqSetCard {
  id: string
  slug: string
  title: string
  description: string
  set_kind: SetKind
  delivery: DeliveryMode
  source_name: string
  source_url: string
  subject_key: string
  chapter_key: string
  term_code: string
  question_count: number
  est_minutes: number
  verified: boolean
  featured: boolean
}

export interface McqSetDetail extends McqSetCard {
  collection_id: string | null
  source_ref: string
  published_at: string | null
}

export interface ExternalLogPayload {
  set_id: string
  score: number
  max_score: number
  taken_on: string
  client_id?: string
}

export interface StartQuickPracticePayload {
  chapter_id?: string
  subject_key?: string
  count?: number
  mode?: 'untimed' | 'timed' | 'chapter_quiz' | 'revision'
  client_id?: string
}

export interface AdaptiveStartPayload {
  scope_type: 'chapter' | 'subject'
  scope_id: string
  subject_key: string
  chapter_key?: string
  client_id?: string
}

export interface AnswerInsightInput {
  result: 'correct' | 'incorrect' | 'partial' | 'skipped'
  confidence: 1 | 2 | 3 | null // 1: sure, 2: unsure, 3: guess
  marks_max: number
  negative_max: number
  marks_awarded: number
  negative_applied: number
}

export interface ConfidenceBandStats {
  count: number
  correct_count: number
  accuracy_pct: number
  net_marks: number
  paying_off: boolean | null
}

export interface NegativeInsightReport {
  total_penalties: number
  penalised_count: number
  break_even_pct: number | null
  sure_but_wrong_count: number
  sure: ConfidenceBandStats
  unsure: ConfidenceBandStats
  guess: ConfidenceBandStats
}

export const mcqFilterSchema = z.object({
  subject: z.string().optional(),
  chapter: z.string().optional(),
  kind: z.string().optional(),
  term: z.string().optional(),
  delivery: z.string().optional(),
})

export type McqFilter = z.infer<typeof mcqFilterSchema>
