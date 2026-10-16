/** Signed-in destinations. A flag hides the link until that feature is on for this student. */
export type WorkspaceFlag =
  | 'focus_timer'
  | 'time_tracker'
  | 'syllabus_coverage'
  | 'notifications_ui'
  | 'notes'
  | 'recall_system'
  | 'today_plan'
  | 'today_planner'
  | 'question_bank'
  | 'pyq_bank'
  | 'mcq_bank'

/** A page inside a section. Shown under its section in the sidebar while that section is open. */
export interface WorkspaceSubLink {
  to:
    | '/app/focus/history'
    | '/app/tracker/log'
    | '/app/tracker/goals'
    | '/app/tracker/reports'
    | '/app/notes/library'
    | '/app/notes/search'
    | '/app/notes/trash'
    | '/app/recall/review'
    | '/app/recall/cards'
    | '/app/recall/decks'
    | '/app/recall/chapters'
    | '/app/recall/forgotten'
    | '/app/recall/suggestions'
    | '/app/recall/stats'
    | '/app/practice/new'
    | '/app/practice/bookmarks'
    | '/app/practice/mistakes'
    | '/app/mcq/sets'
  label: string
}

export interface WorkspaceLink {
  to:
    | '/app/revision'
    | '/app/practice'
    | '/app/notifications'
    | '/app/settings/recall'
    | '/app/today'
    | '/app/planner'
    | '/app/focus'
    | '/app/tracker'
    | '/app/syllabus'
    | '/app/notes'
    | '/app/recall'
    | '/app/questions'
    | '/app/pyq'
    | '/app/mcq'
    | '/app/settings/today'
    | '/app/settings/focus'
    | '/app/settings/tracker'
    | '/app/settings/coverage'
    | '/app/settings/notes'
    | '/app/settings/notifications'
    | '/app/account'
  label: string
  description?: string
  flag?: WorkspaceFlag
  /** Pages inside this section, listed under it while the section is open. */
  children?: readonly WorkspaceSubLink[]
  /** Which sidebar section a study link lives in. Settings links have none. */
  group?: NavGroup
}

export type NavGroup = 'plan' | 'learn' | 'practice'

/** Sidebar sections in order. */
export const NAV_GROUPS: ReadonlyArray<{ id: NavGroup; label: string }> = [
  { id: 'plan', label: 'Plan' },
  { id: 'learn', label: 'Learn' },
  { id: 'practice', label: 'Practice' },
]

export const STUDY_LINKS: readonly WorkspaceLink[] = [
  {
    to: '/app/today',
    group: 'plan',
    label: 'Today',
    description: 'Your tasks for today, paper by paper.',
    flag: 'today_plan',
  },
  {
    to: '/app/planner',
    group: 'plan',
    label: 'Study plan',
    description: 'Your plan to the exam, and whether you are on track.',
    flag: 'today_planner',
  },
  {
    to: '/app/focus',
    group: 'plan',
    label: 'Focus timer',
    description: 'Study in focused rounds, then rest.',
    flag: 'focus_timer',
    children: [{ to: '/app/focus/history', label: 'History' }],
  },
  {
    to: '/app/tracker',
    group: 'plan',
    label: 'Time tracker',
    description: 'Log hours and see where today went.',
    flag: 'time_tracker',
    children: [
      { to: '/app/tracker/log', label: 'Log time' },
      { to: '/app/tracker/goals', label: 'Goals' },
      { to: '/app/tracker/reports', label: 'Reports' },
    ],
  },
  {
    to: '/app/syllabus',
    group: 'plan',
    label: 'My coverage',
    description: 'Tick chapters and see what is left.',
    flag: 'syllabus_coverage',
  },
  {
    to: '/app/revision',
    group: 'learn',
    label: 'Due for revision',
    description: 'Chapters to revise today.',
    flag: 'syllabus_coverage',
  },
  {
    to: '/app/notifications',
    group: 'plan',
    label: 'Inbox',
    description: 'Reminders and updates.',
    flag: 'notifications_ui',
  },
  {
    to: '/app/notes',
    group: 'learn',
    label: 'Notes',
    description: 'Write notes and find them by chapter.',
    flag: 'notes',
    children: [
      { to: '/app/notes/library', label: 'PDF library' },
      { to: '/app/notes/search', label: 'Search' },
      { to: '/app/notes/trash', label: 'Trash' },
    ],
  },
  {
    to: '/app/recall',
    group: 'learn',
    label: 'Revision',
    description: 'Flashcards that come back just before you forget.',
    flag: 'recall_system',
    children: [
      { to: '/app/recall/review', label: 'Review' },
      { to: '/app/recall/cards', label: 'Cards' },
      { to: '/app/recall/decks', label: 'Decks' },
      { to: '/app/recall/chapters', label: 'Chapters' },
      { to: '/app/recall/forgotten', label: 'Forgotten' },
      { to: '/app/recall/suggestions', label: 'Suggestions' },
      { to: '/app/recall/stats', label: 'Stats' },
    ],
  },
  {
    to: '/app/practice',
    group: 'practice',
    label: 'Practice',
    description: 'Build a practice session, then review your answers.',
    flag: 'question_bank',
    children: [
      { to: '/app/practice/new', label: 'New session' },
      { to: '/app/practice/bookmarks', label: 'Bookmarks' },
      { to: '/app/practice/mistakes', label: 'Mistakes' },
    ],
  },
  {
    to: '/app/questions',
    group: 'practice',
    label: 'Questions',
    description: 'Practise and review curated syllabus questions.',
    flag: 'question_bank',
  },
  {
    to: '/app/pyq',
    group: 'practice',
    label: 'Past papers',
    description: 'Previous year exam papers and suggested answers.',
    flag: 'pyq_bank',
  },
  {
    to: '/app/mcq',
    group: 'practice',
    label: 'MCQ Bank',
    description: 'Targeted multiple choice practice and ICMAI booklets.',
    flag: 'mcq_bank',
    children: [{ to: '/app/mcq/sets', label: 'Sets' }],
  },
]

/** Header tabs for editors and admins. Everyone else never sees them (the API checks the role too). */
export const STAFF_LINKS: ReadonlyArray<{ to: '/app/questions/editor' | '/design-system'; label: string }> = [
  { to: '/app/questions/editor', label: 'Editorial queue' },
  { to: '/design-system', label: 'Design system' },
]

export const SETTINGS_LINKS: readonly WorkspaceLink[] = [
  { to: '/app/settings/today', label: 'Today settings', flag: 'today_plan' },
  { to: '/app/settings/focus', label: 'Focus settings', flag: 'focus_timer' },
  { to: '/app/settings/tracker', label: 'Tracker settings', flag: 'time_tracker' },
  { to: '/app/settings/coverage', label: 'Coverage settings', flag: 'syllabus_coverage' },
  { to: '/app/settings/notes', label: 'Notes settings', flag: 'notes' },
  { to: '/app/settings/recall', label: 'Revision settings', flag: 'recall_system' },
  { to: '/app/settings/notifications', label: 'Notification settings', flag: 'notifications_ui' },
  { to: '/app/account', label: 'Account' },
]

const ALL_ON: Record<WorkspaceFlag, boolean> = {
  focus_timer: true,
  time_tracker: true,
  syllabus_coverage: true,
  notifications_ui: true,
  notes: true,
  recall_system: true,
  today_plan: true,
  today_planner: true,
  question_bank: true,
  pyq_bank: true,
  mcq_bank: true,
}

/** Keep links whose flag is on. Links with no flag always stay. */
export function visibleLinks(
  links: readonly WorkspaceLink[],
  enabled: Record<WorkspaceFlag, boolean> = ALL_ON,
): WorkspaceLink[] {
  return links.filter((link) => link.flag === undefined || enabled[link.flag])
}
