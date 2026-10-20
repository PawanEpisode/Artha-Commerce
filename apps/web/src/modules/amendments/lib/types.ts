export type ApplicabilityStatus = 'applies' | 'not_applicable' | 'unknown'

export interface Applicability {
  state: ApplicabilityStatus
  reason: string
}

export interface DocumentTermRule {
  term_code: string
  applicability: 'applies' | 'excluded'
  cutoff_date: string | null
  cutoff_note?: string
  source_page?: number | null
}

export interface ApplicabilityResult {
  status: ApplicabilityStatus
  reason_code: string
  reason_text: string
}

export type ChangeType = 'addition' | 'deletion' | 'modification' | 'new_standard' | 'clarification'

export type Materiality = 'high' | 'normal' | 'low'
export type RevisionEffect = 'new' | 'unchanged' | 'updated' | 'removed'

export interface CardMapping {
  subject_key: string
  chapter_key: string
  chapter_name?: string
  is_primary: boolean
  coverage_pct?: number
  status?: string
}

export interface DocumentSummary {
  slug: string
  title: string
  issuer_label?: string
  official_url: string
  issued_on?: string | null
}

export interface MyCard {
  public_id: string
  card_key: string
  change_type: ChangeType
  law_label: string
  provision_label: string
  title: string
  summary_old?: string | null
  summary_new?: string | null
  effective_text: string
  source_page: number
  materiality: Materiality
  revision_effect: RevisionEffect
  subject_key: string
  applicability: Applicability
  is_reviewed: boolean
  is_saved: boolean
  is_updated: boolean
  document: DocumentSummary
  mappings: CardMapping[]
}

export interface PaperBreakdown {
  subject_key: string
  total: number
  reviewed: number
}

export interface MySummary {
  target_term: string | null
  total_cards_count: number
  reviewed_count: number
  saved_count: number
  breakdown_by_paper: PaperBreakdown[]
  breakdown_by_type: Record<string, number>
}

export interface CardFilter {
  applies?: 'mine' | 'all'
  subject?: string
  type?: ChangeType | ''
  state?: 'unreviewed' | 'reviewed' | 'saved' | ''
  term?: string
  q?: string
}

export interface TermArchiveRow {
  term_code: string
  documents_count: number
  cards_count: number
  applicability: ApplicabilityStatus
}

export interface ChapterCard {
  public_id: string
  card_key: string
  title: string
  provision_label: string
  change_type: ChangeType
  summary_new: string
  summary_old?: string | null
  materiality: Materiality
  source_page: number
  applicability: Applicability
  document_slug: string
  official_url: string
}

export interface PublicTermRule {
  term_code: string
  applicability: 'applies' | 'excluded'
  cutoff_date: string | null
}

export interface PublicCard {
  public_id: string
  card_key: string
  tombstone: boolean
  status: string
  change_type: ChangeType
  law_label: string
  law_key: string
  provision_label: string
  title: string
  summary_old?: string | null
  summary_new?: string | null
  effective_text: string
  effective_from_term_code?: string | null
  source_page: number
  materiality: Materiality
  document: DocumentSummary
  terms: PublicTermRule[]
  chapters: Array<{
    subject_key: string
    chapter_key: string
    chapter_name?: string
    is_primary: boolean
  }>
  notice?: string
}

export interface PublicDocument {
  slug: string
  title: string
  short_title?: string
  issuer_label: string
  kind: string
  course: string
  level: string
  revision_no: number
  issued_on?: string | null
  official_url: string
  terms: PublicTermRule[]
  papers: string[]
  notice?: string
  cards?: PublicCard[]
}

export interface PublicHub {
  latest_documents: PublicDocument[]
  courses: Array<{
    code: string
    name: string
    levels: Array<{ code: string; name: string }>
  }>
}
