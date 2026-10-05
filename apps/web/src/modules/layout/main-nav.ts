export interface MainNavItem {
  to: '/features' | '/courses'
  label: string
}

/** Public links sit on the right of the header. Courses is only for a signed-out visitor. */
export function mainNav(signedIn: boolean): MainNavItem[] {
  const items: MainNavItem[] = [{ to: '/features', label: 'Features' }]
  if (!signedIn) items.push({ to: '/courses', label: 'Courses' })
  return items
}
