/** Shapes returned by the public syllabus API (`/api/v1/syllabus/...`). */

export interface SyllabusScheme {
  id: string
  code: string
  name: string
  status: 'draft' | 'published' | 'retired'
  from_term: string | null
  to_term: string | null
  source_url: string
  published_at: string | null
}

export interface SyllabusGroup {
  id: string
  key: string
  name: string
  sort_order: number
}

export interface SyllabusSubject {
  id: string
  key: string
  paper_number: number | null
  name: string
  total_marks: number | null
  exam_duration_minutes: number | null
  kind: string
  is_optional: boolean
  sort_order: number
  group_key: string | null
  chapter_count: number
}

export interface SyllabusChapter {
  id: string
  key: string
  name: string
  marks_min: string | null
  marks_max: string | null
  marks_weight: number
  weight_source: string
  target_practice_sets: number
  target_revisions: number
  target_mocks: number
  est_study_minutes: number | null
  sort_order: number
}

export interface SyllabusTopic {
  id: string
  key: string
  name: string
  kind: string
  sort_order: number
}

export interface LevelSyllabus {
  id: string
  code: string
  name: string
  sort_order: number
  course: { code: string; name: string; institute_name: string; institute_url: string }
  scheme: SyllabusScheme | null
  schemes: SyllabusScheme[]
  groups: SyllabusGroup[]
  subjects: SyllabusSubject[]
}

export interface SubjectSyllabus extends SyllabusSubject {
  course: string
  level: string
  scheme: SyllabusScheme
  chapters: SyllabusChapter[]
}

export interface ChapterSyllabus extends SyllabusChapter {
  course: string
  level: string
  subject: SyllabusSubject
  topics: SyllabusTopic[]
}

export type ReportNodeType = 'course' | 'level' | 'scheme' | 'subject' | 'chapter' | 'topic'

export interface CourseSummary {
  id: string
  code: string
  name: string
  institute_name: string
  institute_url: string
  description: string
  levels: Array<{ id: string; code: string; name: string; sort_order: number }>
}

export interface ExamTerm {
  id: string
  course: string
  code: string
  name: string
  exam_start: string | null
  exam_end: string | null
}
