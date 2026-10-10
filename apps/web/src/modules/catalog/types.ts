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
  | 'study-time'
  | 'bell-ring'

export type LiveToolPath =
  '/app/focus' | '/app/syllabus' | '/app/tracker' | '/app/tracker/reports' | '/app/notes' | '/app/recall'

export type FeatureFlagName = 'focus_timer' | 'time_tracker' | 'syllabus_coverage' | 'notes' | 'recall_system'

/** Where a shipped tool opens. Absent on features that are not built yet. */
export interface FeatureTool {
  to: LiveToolPath
  /** Imperative label, e.g. "Start a focus round". */
  cta: string
  /** Hidden for a student when this flag is explicitly off. */
  flag: FeatureFlagName
  /** A public page that is useful before sign-in. */
  browse?: { to: '/courses'; label: string }
}

interface FeatureBase {
  slug: string
  title: string
  tagline: string
  description: string
  icon: FeatureIconKey
  highlights: string[]
}

export type Feature = (FeatureBase & { status: 'live'; tool: FeatureTool }) | (FeatureBase & { status: 'soon' })
