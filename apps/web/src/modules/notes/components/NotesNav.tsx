import { SectionTabs } from '@artha/design-system'
import { Link, useRouterState } from '@tanstack/react-router'

import { useFeatureFlag } from '~/modules/observability'

import { useContinueReading } from '../hooks/useLibrary'
import { isFeatureDisabled } from '../lib/errors'

const ITEMS = [
  { value: 'notes', label: 'My notes', to: '/app/notes' },
  { value: 'library', label: 'Library', to: '/app/notes/library' },
  { value: 'search', label: 'Search', to: '/app/notes/search' },
  { value: 'trash', label: 'Trash', to: '/app/notes/trash' },
  { value: 'settings', label: 'Notes settings', to: '/app/settings/notes' },
] as const

type Section = (typeof ITEMS)[number]['value']

/** Which tab a path belongs to. Exported for the test. */
export const sectionOf = (pathname: string): Section =>
  pathname.startsWith('/app/notes/library')
    ? 'library'
    : pathname.startsWith('/app/notes/search')
      ? 'search'
      : pathname.startsWith('/app/notes/trash')
        ? 'trash'
        : pathname.startsWith('/app/settings')
          ? 'settings'
          : 'notes'

/** Sticky local navigation for the notes screens: the shared `SectionTabs`, each tab a real route. */
export function NotesNav() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  // The Library entry is hidden while PDFs are off: the web flag, or the API answering 403 `feature_disabled`.
  const pdf = useFeatureFlag('notes_pdf')
  const probe = useContinueReading(pdf)
  const items = pdf && !isFeatureDisabled(probe.error) ? ITEMS : ITEMS.filter((i) => i.value !== 'library')
  return (
    <SectionTabs
      label="Notes"
      items={items.map(({ value, label, to }) => ({ value, label, href: to }))}
      value={sectionOf(pathname)}
      className="[&>div]:mx-auto [&>div]:max-w-4xl"
      renderLink={(item, props) => {
        const target = items.find((i) => i.value === item.value)
        return target ? <Link to={target.to} {...props} /> : null
      }}
    />
  )
}
