// F-12 Institute Study Material (MAT) Types

export type RightsLevel = 'L0' | 'L1' | 'L2' | 'L3' | 'L4'

export type ItemKind = 'illustration' | 'concept' | 'exercise' | 'tyk' | 'mcq' | 'case_study' | 'practical'

export type ProgressState = 'to_do' | 'done' | 'revise'

export interface Provider {
  id: string
  code: string
  name: string
  full_name: string
  country: string
  official_portal_url: string
  default_rights_level: RightsLevel
  is_active: boolean
  is_followed?: boolean
  is_primary?: boolean
}

export interface Work {
  id: string
  work_key: string
  slug: string
  title: string
  course: string
  level: string | number
  subject_code?: string
  subject_key?: string
  kind?: string
  provider: Provider
  current_edition?: EditionSummary | null
  edition?: EditionSummary | null
  editions_count?: number
  chapters_count?: number
  item_count?: number
}

export interface EditionSummary {
  id: string
  edition_key: string
  term_code?: string
  publication_year?: number
  label: string
  is_current?: boolean
  rights_level?: RightsLevel
  pdf_url?: string | null
  source_url?: string | null
  page_offset?: number
  units?: UnitDetail[]
}

export interface EditionDetail extends EditionSummary {
  work_id: string
  work_slug: string
  work_title: string
  units: UnitDetail[]
}

export interface UnitDetail {
  id: string
  title: string
  unit_number: number
  chapters: ChapterDetail[]
}

export interface ChapterDetail {
  id: string
  chapter_key: string
  title: string
  sequence_order: number
  items_count: number
  summary?: ChapterSummary
}

export interface MaterialItem {
  id: string
  stable_key: string
  kind: ItemKind
  canonical_label: string
  title: string
  content_markdown?: string
  content_html?: string
  official_page?: number | null
  solution_page?: number | null
  rights_level: RightsLevel
  created_at?: string
  // User interaction & progress
  progress?: ProgressState
  note?: string
  revised_since_done?: boolean
  deep_link?: string | null
}

export interface ChapterItemsResponse {
  chapter_key: string
  chapter_title: string
  work_slug: string
  work_title: string
  edition_label: string
  items: MaterialItem[]
  summary: ChapterSummary
}

export interface ChapterSummary {
  total: number
  done: number
  revise: number
  to_do: number
  completion_pct: number
  revised_badge: boolean
}

export type ChangeType = 'added' | 'removed' | 'modified' | 'reordered' | 'unchanged'

export interface EditionDiffItem {
  stable_key: string
  kind: ItemKind
  canonical_label: string
  title: string
  change_type: ChangeType
  old_page?: number | null
  new_page?: number | null
  notes?: string
}

export interface CompareResult {
  from_edition: string
  to_edition: string
  summary: {
    total_items: number
    added: number
    removed: number
    modified: number
    reordered: number
    unchanged: number
  }
  items: EditionDiffItem[]
}

export interface UserProviderFollow {
  id: string
  provider_id: string
  provider_code: string
  provider_name: string
  is_primary: boolean
  created_at: string
}

export interface UserEditionSelection {
  id: string
  work_id: string
  work_slug: string
  work_title: string
  edition_id: string
  edition_key: string
  edition_label: string
  is_active: boolean
}

export interface MaterialReportPayload {
  item_id: string
  report_type: 'broken_link' | 'wrong_mapping' | 'typo' | 'missing_content' | 'other'
  description: string
}
