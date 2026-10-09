import { SectionTabs } from '@artha/design-system'
import { Link, useRouterState } from '@tanstack/react-router'

import { activeSection, RECALL_SECTIONS } from '../lib/sections'

/** Local navigation of the recall area: the design-system tabs wired to the router. The URL decides the active tab. */
export function RouterSectionTabs() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const hrefs = new Map(RECALL_SECTIONS.map((i) => [i.value, i.to]))
  return (
    <SectionTabs
      label="Revision sections"
      items={RECALL_SECTIONS.map((i) => ({ value: i.value, label: i.label, href: i.to }))}
      value={activeSection(pathname, RECALL_SECTIONS) ?? ''}
      className="[&>div]:mx-auto [&>div]:max-w-3xl"
      renderLink={(item, props) => {
        const to = hrefs.get(item.value)
        return to ? <Link to={to} {...props} /> : null
      }}
    />
  )
}
