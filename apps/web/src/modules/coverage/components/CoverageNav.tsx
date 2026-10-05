import { Badge, SectionTabs } from '@artha/design-system'
import { Link, useRouterState } from '@tanstack/react-router'

const ITEMS = [
  { value: 'map', label: 'Syllabus map', to: '/app/syllabus' },
  { value: 'revision', label: 'Due for revision', to: '/app/revision' },
  { value: 'settings', label: 'Coverage settings', to: '/app/settings/coverage' },
] as const

type Section = (typeof ITEMS)[number]['value']

const sectionOf = (pathname: string): Section =>
  pathname.startsWith('/app/revision') ? 'revision' : pathname.startsWith('/app/settings') ? 'settings' : 'map'

/** Sticky local navigation for My Coverage screens: the shared `SectionTabs`, each tab a real route. */
export function CoverageNav({ dueCount }: { dueCount?: number }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  return (
    <SectionTabs
      label="My Coverage"
      items={ITEMS.map(({ value, label, to }) => ({ value, label, href: to }))}
      value={sectionOf(pathname)}
      className="[&>div]:mx-auto [&>div]:max-w-3xl"
      renderLink={(item, props) => {
        const target = ITEMS.find((i) => i.value === item.value)
        if (!target) return null
        const { children, ...rest } = props
        return (
          <Link to={target.to} {...rest}>
            {children}
            {target.value === 'revision' && dueCount ? <Badge variant="highlight">{dueCount}</Badge> : null}
          </Link>
        )
      }}
    />
  )
}
