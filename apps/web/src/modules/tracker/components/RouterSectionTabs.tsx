import { SectionTabs } from '@artha/design-system'
import { Link, useRouterState } from '@tanstack/react-router'

import { activeSection, type SectionLink } from '../lib/sections'

/**
 * The shared sticky sub-navigation of the tracker and focus areas: design-system `SectionTabs` wired to the router.
 * The active tab follows the URL, so the bar never needs state of its own.
 */
const WIDTH = { '3xl': '[&>div]:mx-auto [&>div]:max-w-3xl', '4xl': '[&>div]:mx-auto [&>div]:max-w-4xl' } as const

export function RouterSectionTabs({
  label,
  items,
  width = '4xl',
}: {
  label: string
  items: ReadonlyArray<SectionLink>
  /** Match the page's container so the tabs line up with the content. */
  width?: keyof typeof WIDTH
}) {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const hrefs = new Map(items.map((i) => [i.value, i.to]))
  return (
    <SectionTabs
      label={label}
      items={items.map((i) => ({ value: i.value, label: i.label, href: i.to }))}
      value={activeSection(pathname, items) ?? ''}
      className={WIDTH[width]}
      renderLink={(item, props) => {
        const to = hrefs.get(item.value)
        return to ? <Link to={to} {...props} /> : null
      }}
    />
  )
}
