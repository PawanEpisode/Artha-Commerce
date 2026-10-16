import type { WorkspaceLink } from './workspace-nav'

export interface Section {
  to: string
  label: string
}

const HOME: Section = { to: '/app', label: 'Home' }

const withoutTrailingSlash = (path: string) => (path.length > 1 ? path.replace(/\/+$/, '') : path)

/** True for the pages that live in the Settings area (the settings pages and the account page). */
export const isSettingsPath = (pathname: string): boolean => {
  const path = withoutTrailingSlash(pathname)
  return path === '/app/account' || path === '/app/settings' || path.startsWith('/app/settings/')
}

/** The sidebar section a path belongs to: the longest matching link prefix, Settings for the settings area, else Home. */
export function currentSection(pathname: string, links: readonly WorkspaceLink[]): Section {
  const path = withoutTrailingSlash(pathname)
  if (path === '/features' || path.startsWith('/features/')) return { to: '/features', label: 'Features' }
  if (path === '/courses' || path.startsWith('/courses/')) return { to: '/courses', label: 'Courses' }
  if (isSettingsPath(path)) return { to: '/app/account', label: 'Settings' }
  let best: Section | undefined
  for (const link of links) {
    const hit = path === link.to || path.startsWith(`${link.to}/`)
    if (hit && (!best || link.to.length > best.to.length)) best = { to: link.to, label: link.label }
  }
  return best ?? HOME
}

/** Short label for a settings link: "Focus settings" -> "Focus". */
export const settingsLabel = (link: WorkspaceLink): string => link.label.replace(/ settings$/i, '')
