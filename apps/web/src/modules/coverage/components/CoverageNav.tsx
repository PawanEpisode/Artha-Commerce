import { Badge, Button } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

/** Local navigation for My Coverage screens. Each tab is a real route. */
export function CoverageNav({ dueCount }: { dueCount?: number }) {
  const items: Array<{
    to: '/app/syllabus' | '/app/revision' | '/app/settings/coverage'
    label: string
    badge?: number
  }> = [
    { to: '/app/syllabus', label: 'Syllabus map' },
    { to: '/app/revision', label: 'Due for revision', badge: dueCount },
    { to: '/app/settings/coverage', label: 'Coverage settings' },
  ]
  return (
    <nav aria-label="My Coverage" className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
      {items.map((item) => (
        <Button key={item.to} variant="ghost" size="sm" className="shrink-0" asChild>
          <Link
            to={item.to}
            activeOptions={{ exact: item.to === '/app/syllabus' ? false : true }}
            activeProps={{ className: 'bg-secondary text-secondary-foreground', 'aria-current': 'page' }}
          >
            {item.label}
            {item.badge ? <Badge variant="highlight">{item.badge}</Badge> : null}
          </Link>
        </Button>
      ))}
    </nav>
  )
}
