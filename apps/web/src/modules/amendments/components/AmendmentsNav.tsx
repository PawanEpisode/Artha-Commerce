import { SectionTabs } from '@artha/design-system'
import { Link, useRouterState } from '@tanstack/react-router'

const ITEMS = [
  { value: 'current', label: 'My Amendments', to: '/app/amendments' },
  { value: 'archive', label: 'Term Archive', to: '/app/amendments/archive' },
] as const

type Section = (typeof ITEMS)[number]['value']

export const sectionOf = (pathname: string): Section =>
  pathname.startsWith('/app/amendments/archive') ? 'archive' : 'current'

export function AmendmentsNav() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  return (
    <SectionTabs
      label="Amendments"
      items={ITEMS.map(({ value, label, to }) => ({ value, label, href: to }))}
      value={sectionOf(pathname)}
      renderLink={(item, props) => {
        const target = ITEMS.find((i) => i.value === item.value)
        return target ? <Link to={target.to} {...props} /> : null
      }}
    />
  )
}
