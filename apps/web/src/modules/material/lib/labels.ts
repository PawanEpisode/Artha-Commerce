import type { ItemKind, ProgressState, RightsLevel } from './types'

export function getKindMetadata(kind: ItemKind): { label: string; shortLabel: string; color: string } {
  switch (kind) {
    case 'illustration':
      return {
        label: 'Illustration',
        shortLabel: 'Illus',
        color: 'bg-blue-50 text-blue-700 border-blue-200',
      }
    case 'concept':
      return {
        label: 'Concept Note',
        shortLabel: 'Concept',
        color: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      }
    case 'exercise':
      return {
        label: 'Practical Exercise',
        shortLabel: 'Exercise',
        color: 'bg-purple-50 text-purple-700 border-purple-200',
      }
    case 'tyk':
      return {
        label: 'Test Your Knowledge',
        shortLabel: 'TYK',
        color: 'bg-amber-50 text-amber-800 border-amber-200',
      }
    case 'mcq':
      return {
        label: 'Multiple Choice Question',
        shortLabel: 'MCQ',
        color: 'bg-sky-50 text-sky-700 border-sky-200',
      }
    case 'case_study':
      return {
        label: 'Case Study',
        shortLabel: 'Case',
        color: 'bg-indigo-50 text-indigo-700 border-indigo-200',
      }
    case 'practical':
      return {
        label: 'Comprehensive Problem',
        shortLabel: 'Problem',
        color: 'bg-violet-50 text-violet-700 border-violet-200',
      }
    default:
      return {
        label: kind,
        shortLabel: kind,
        color: 'bg-muted text-muted-foreground border-border',
      }
  }
}

export function getProgressMetadata(state?: ProgressState): {
  label: string
  color: string
  activeColor: string
} {
  switch (state) {
    case 'done':
      return {
        label: 'Done',
        color: 'bg-emerald-50 text-emerald-700 border-emerald-200',
        activeColor: 'bg-emerald-600 text-white border-emerald-600',
      }
    case 'revise':
      return {
        label: 'Revise',
        color: 'bg-amber-50 text-amber-700 border-amber-200',
        activeColor: 'bg-amber-600 text-white border-amber-600',
      }
    case 'to_do':
    default:
      return {
        label: 'To Do',
        color: 'bg-muted/40 text-muted-foreground border-border',
        activeColor: 'bg-foreground text-background border-foreground',
      }
  }
}

export function formatTermCode(termCode: string): string {
  if (!termCode || termCode.length < 3) return termCode
  const prefix = termCode[0].toUpperCase()
  const yearSuffix = termCode.slice(1)
  const fullYear = `20${yearSuffix}`

  switch (prefix) {
    case 'M':
      return `May ${fullYear}`
    case 'N':
      return `Nov ${fullYear}`
    case 'J':
      return `June ${fullYear}`
    case 'D':
      return `Dec ${fullYear}`
    case 'S':
      return `Sept ${fullYear}`
    default:
      return termCode
  }
}

export function getRightsDescription(level: RightsLevel): {
  title: string
  description: string
  isHosted: boolean
  isDeepLink: boolean
} {
  switch (level) {
    case 'L0':
      return {
        title: 'Metadata Only',
        description: 'Citation and catalog index only. Content is not stored on Artha.',
        isHosted: false,
        isDeepLink: false,
      }
    case 'L1':
      return {
        title: 'Deep-Linked to Official Portal',
        description: 'Direct deep-link to official Institute PDF page. Artha stores no copy.',
        isHosted: false,
        isDeepLink: true,
      }
    case 'L2':
      return {
        title: 'Permitted Fair-Use Snippets',
        description: 'Short excerpts and references with full attribution under statutory exception.',
        isHosted: true,
        isDeepLink: true,
      }
    case 'L3':
      return {
        title: 'Full CC-BY / Open Content',
        description: 'Complete text and solutions under open educational license.',
        isHosted: true,
        isDeepLink: false,
      }
    case 'L4':
      return {
        title: 'Direct Institute Partner Licensed',
        description: 'Official direct publisher partnership with full digital rights.',
        isHosted: true,
        isDeepLink: false,
      }
  }
}
