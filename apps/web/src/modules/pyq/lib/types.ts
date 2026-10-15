import { z } from 'zod'

export type SchemeRelation = 'current' | 'mapped' | 'changed' | 'unmapped'
export type DeliveryMode = 'link_out' | 'pdf_only' | 'digitised_interactive'
export type AnswersStatus = 'full' | 'partial' | 'unreleased'
export type RuleKind = 'compulsory' | 'any_n_of_m' | 'either_or'

export interface PyqPaperCard {
  id: string
  external_ref: string
  course_code: string
  level_code: string
  subject_key: string
  term_code: string
  title: string
  paper_code: string
  duration_minutes: number | null
  total_marks: string
  delivery: DeliveryMode
  answers_status: AnswersStatus
  syllabus_status: string
  status: string
  question_count: number
  attempted_count: number
  correct_count: number
}

export interface PyqPaperLink {
  id: string
  link_kind: string
  label: string
  url: string
  host: string
  page_hint: string
  link_status: string
  verified: boolean
}

export interface PyqChoiceGroup {
  id: string
  label: string
  rule_kind: RuleKind
  pick_count: number
  of_count: number
  section_label: string
  sort_order: number
}

export interface PyqPaperQuestion {
  id: string
  parent_id: string | null
  number_label: string
  depth: number
  sort_order: number
  is_leaf: boolean
  question_id: string | null
  marks: string
  kind: string
  descriptor: string
  chapter_id: string | null
  chapter_key: string | null
  scheme_relation: SchemeRelation
  answer_source: string
  answer_page_hint: string
  source_page_hint: string
  choice_group_id: string | null
  choice_group_label: string | null
  section_label: string | null
  user_state?: {
    attempts: number
    correct_count: number
    last_result: string | null
    bookmarked: boolean
    box?: number
  } | null
}

export interface PyqPaperDetail {
  id: string
  external_ref: string
  course_code: string
  level_code: string
  subject_key: string
  term_code: string
  title: string
  paper_code: string
  duration_minutes: number | null
  reading_minutes: number | null
  total_marks: string
  marks_note: string
  law_note: string
  delivery: DeliveryMode
  answers_status: AnswersStatus
  syllabus_status: string
  source_name: string
  status: string
  question_count: number
  links: PyqPaperLink[]
  choice_groups: PyqChoiceGroup[]
  questions: PyqPaperQuestion[]
}

export interface ChapterPyqItem {
  id: string
  question_id: string
  paper_id: string
  paper_title: string
  term_code: string
  number_label: string
  marks: string
  kind: string
  descriptor: string
  scheme_relation: SchemeRelation
  answer_page_hint: string
  user_state?: {
    attempts: number
    correct_count: number
    last_result: string | null
    bookmarked: boolean
  } | null
}

export interface PaperFilterParams {
  course?: string
  level?: string
  subject?: string
  term?: string
  status?: string
}

export const pyqSearchSchema = z.object({
  course: z.string().optional(),
  level: z.string().optional(),
  subject: z.string().optional(),
  term: z.string().optional(),
  q: z.string().optional(),
})

export type PyqSearch = z.infer<typeof pyqSearchSchema>
