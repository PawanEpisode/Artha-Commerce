import { Button } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { useWorkspaceNav } from './useWorkspaceNav'
import { workspaceIcon } from './workspace-icons'

function LinkRow({
  label,
  items,
  variant,
}: {
  label: string
  items: ReturnType<typeof useWorkspaceNav>['study']
  variant: 'secondary' | 'outline'
}) {
  if (items.length === 0) return null
  return (
    <nav aria-label={label}>
      <ul className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        {items.map((item) => {
          const Icon = workspaceIcon(item.to)
          return (
            <li key={item.to}>
              <Button variant={variant} className="w-full justify-start sm:w-auto" asChild>
                <Link to={item.to}>
                  <Icon aria-hidden />
                  {item.label}
                </Link>
              </Button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

/** The last section of the workspace home: every study tool and setting in one compact place. */
export function ToolsAndSettings() {
  const { study, settings } = useWorkspaceNav()
  return (
    <section aria-labelledby="tools-heading" className="space-y-4">
      <h2 id="tools-heading" className="text-lg font-bold">
        Tools and settings
      </h2>
      <LinkRow label="Study tools" items={study} variant="secondary" />
      <LinkRow label="Settings" items={settings} variant="outline" />
    </section>
  )
}
