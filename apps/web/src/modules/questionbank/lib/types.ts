import { z } from 'zod'

export type QuestionKind =
  'mcq_single' | 'mcq_multi' | 'true_false' | 'numeric' | 'case_study' | 'long_form' | 'practical'

export type QuestionNature = 'theory' | 'practical' | 'formula' | 'section' | 'case_law' | 'application'

export interface QuestionCardData {
  id: string
  public_id: string
  kind: QuestionKind
  stem_head: string
  marks: number
  difficulty: number
  nature: QuestionNature
  source_name?: string
  source_year?: number
  source_term_code?: string
  is_verified: boolean
  primary_chapter_id?: string
  chapter_key?: string
  subject_key?: string
  tag_slugs: string[]
  published_at?: string
  // Personal overlay (if present)
  last_result?: 'correct' | 'incorrect' | 'skipped' | 'partial'
  is_bookmarked?: boolean
  has_doubt?: boolean
}

export interface PlayableOption {
  id: string
  body_md: string
  pinned: boolean
}

export interface PlayableQuestion {
  question_id: string
  version_id: string
  version_no: number
  kind: QuestionKind
  position: number
  group?: string
  stem_md: string
  marks: number
  negative_applies: boolean
  suggested_seconds: number
  options: PlayableOption[]
  numeric?: {
    unit?: string
  }
  labels: Record<string, unknown>
  media: string[]
  needs_attention?: boolean
}

export interface ReviewOption extends PlayableOption {
  is_correct?: boolean
}

export interface ReviewQuestion {
  question_id: string
  version_id: string
  version_no: number
  kind: QuestionKind
  position: number
  stem_md: string
  marks: number
  negative_marks: number
  suggested_seconds: number
  options: ReviewOption[]
  correct_option_ids: string[]
  numeric_key?: number
  explanation_md?: string
  explanation_source?: string
  reference_labels?: string[]
  rubric?: {
    total_marks: number
    steps: Array<{ step_no: number; description_md: string; marks: number }>
  }
  labels: Record<string, unknown>
  media: string[]
  newer_version_available?: boolean
}

export interface QuestionFacets {
  kinds: Record<string, number>
  difficulties: Record<number, number>
  years: Record<number, number>
  subjects: Record<string, number>
}

export interface QuestionSearchParams {
  q?: string
  subject?: string
  chapter?: string
  kind?: QuestionKind
  difficulty?: number
  year?: number
  term?: string
  tag?: string
  state?: 'unattempted' | 'wrong' | 'bookmarked'
  cursor?: string
  limit?: number
}

export interface QuestionListResponse {
  items: QuestionCardData[]
  next_cursor?: string
  total_count?: number
}

export const questionsSearchSchema = z.object({
  q: z.string().max(200).optional().catch(undefined),
  subject: z.string().optional().catch(undefined),
  chapter: z.string().optional().catch(undefined),
  kind: z.string().optional().catch(undefined),
  difficulty: z.coerce.number().optional().catch(undefined),
  year: z.coerce.number().optional().catch(undefined),
  term: z.string().optional().catch(undefined),
  tag: z.string().optional().catch(undefined),
  state: z.enum(['unattempted', 'wrong', 'bookmarked']).optional().catch(undefined),
  cursor: z.string().optional().catch(undefined),
})
