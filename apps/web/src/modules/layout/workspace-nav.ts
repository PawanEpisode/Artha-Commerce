/** Signed-in destinations. A flag hides the link until that feature is on for this student. */
export type WorkspaceFlag = 'focus_timer' | 'time_tracker' | 'syllabus_coverage' | 'notifications_ui'

export interface WorkspaceLink {
  to:
    | '/app/focus'
    | '/app/tracker'
    | '/app/syllabus'
    | '/app/settings/focus'
    | '/app/settings/tracker'
    | '/app/settings/coverage'
    | '/app/settings/notifications'
    | '/app/account'
  label: string
  description?: string
  flag?: WorkspaceFlag
}

export const STUDY_LINKS: readonly WorkspaceLink[] = [
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
]

export const SETTINGS_LINKS: readonly WorkspaceLink[] = [
  { to: '/app/settings/focus', label: 'Focus settings', flag: 'focus_timer' },
  { to: '/app/settings/tracker', label: 'Tracker settings', flag: 'time_tracker' },
  { to: '/app/settings/coverage', label: 'Coverage settings', flag: 'syllabus_coverage' },
  { to: '/app/settings/notifications', label: 'Notification settings', flag: 'notifications_ui' },
  { to: '/app/account', label: 'Account' },
]

const ALL_ON: Record<WorkspaceFlag, boolean> = {
  focus_timer: true,
  time_tracker: true,
  syllabus_coverage: true,
  notifications_ui: true,
}

/** Keep links whose flag is on. Links with no flag always stay. */
export function visibleLinks(
  links: readonly WorkspaceLink[],
  enabled: Record<WorkspaceFlag, boolean> = ALL_ON,
): WorkspaceLink[] {
  return links.filter((link) => link.flag === undefined || enabled[link.flag])
}
