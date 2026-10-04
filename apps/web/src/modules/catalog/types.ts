export type CourseSlug = 'ca' | 'cs' | 'cma'

export interface Level {
  slug: string
  name: string
  /** Indicative subject list. Verify against the official syllabus before treating as authoritative. */
  subjects: string[]
}

export interface Course {
  slug: CourseSlug
  name: string
  fullName: string
  body: string
  bodyFullName: string
  tagline: string
  description: string
  levels: Level[]
}

export type FeatureIconKey =
  | 'calendar'
  | 'list-checks'
  | 'timer'
  | 'sparkles'
  | 'notebook-pen'
  | 'layers'
  | 'file-clock'
  | 'flame'
  | 'bell-ring'

export interface Feature {
  slug: string
  title: string
  tagline: string
  description: string
  icon: FeatureIconKey
  highlights: string[]
  status: 'live' | 'soon'
}
