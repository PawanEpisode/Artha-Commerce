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

export interface WorkspaceLink {
  to:
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
}

export const STUDY_LINKS: readonly WorkspaceLink[] = [
  {
    to: '/app/today',
    label: 'Today',
    description: 'Your tasks for today, paper by paper.',
    flag: 'today_plan',
  },
  {
    to: '/app/planner',
    label: 'Study plan',
    description: 'Your plan to the exam, and whether you are on track.',
    flag: 'today_planner',
  },
  {
    to: '/app/focus',
    label: 'Focus timer',
    description: 'Study in focused rounds, then rest.',
    flag: 'focus_timer',
  },
  {
    to: '/app/tracker',
    label: 'Time tracker',
    description: 'Log hours and see where today went.',
    flag: 'time_tracker',
  },
  {
    to: '/app/syllabus',
    label: 'My coverage',
    description: 'Tick chapters and see what is left.',
    flag: 'syllabus_coverage',
  },
  {
    to: '/app/notes',
    label: 'Notes',
    description: 'Write notes and find them by chapter.',
    flag: 'notes',
  },
  {
    to: '/app/recall',
    label: 'Revision',
    description: 'Flashcards that come back just before you forget.',
    flag: 'recall_system',
  },
  {
    to: '/app/questions',
    label: 'Questions',
    description: 'Practise and review curated syllabus questions.',
    flag: 'question_bank',
  },
  {
    to: '/app/pyq',
    label: 'Past papers',
    description: 'Previous year exam papers and suggested answers.',
    flag: 'pyq_bank',
  },
  {
    to: '/app/mcq',
    label: 'MCQ Bank',
    description: 'Targeted multiple choice practice and ICMAI booklets.',
    flag: 'mcq_bank',
  },
]

export const SETTINGS_LINKS: readonly WorkspaceLink[] = [
  { to: '/app/settings/today', label: 'Today settings', flag: 'today_plan' },
  { to: '/app/settings/focus', label: 'Focus settings', flag: 'focus_timer' },
  { to: '/app/settings/tracker', label: 'Tracker settings', flag: 'time_tracker' },
  { to: '/app/settings/coverage', label: 'Coverage settings', flag: 'syllabus_coverage' },
  { to: '/app/settings/notes', label: 'Notes settings', flag: 'notes' },
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
