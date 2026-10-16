import { cn } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { settingsLabel } from './app-nav'
import { useWorkspaceNav } from './useWorkspaceNav'
import { workspaceIcon } from './workspace-icons'

/**
 * Settings are one area, not seven pages in a menu: a side list on desktop (a scrolling row on a phone) that switches
 * between them, so moving from Focus settings to Notes settings is one click.
 */
export function SettingsFrame({ children }: { children: ReactNode }) {
  const { settings } = useWorkspaceNav()
  return (
    <div className="flex min-w-0 flex-col md:flex-row">
      <nav
        aria-label="Settings"
        className="shrink-0 border-b px-4 py-2 md:sticky md:top-11 md:h-[calc(100dvh-2.75rem)] md:w-44 md:self-start md:overflow-y-auto md:border-r md:border-b-0 md:px-2 md:py-3"
      >
        <p className="mb-1 hidden px-2.5 text-[11px] font-medium tracking-wide text-muted-foreground uppercase md:block">
          Settings
        </p>
        <ul className="flex gap-1 overflow-x-auto md:flex-col md:gap-px md:overflow-visible">
          {settings.map((link) => {
            const Icon = workspaceIcon(link.to)
            return (
              <li key={link.to} className="shrink-0">
                <Link
                  to={link.to}
                  className={cn(
                    'flex h-7 items-center gap-2 rounded-md px-2.5 text-[13px] font-medium whitespace-nowrap text-muted-foreground transition-colors outline-none hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 aria-[current=page]:bg-sidebar-accent aria-[current=page]:text-foreground pointer-coarse:h-10 [&_svg]:size-4',
                  )}
                >
                  <Icon aria-hidden />
                  {settingsLabel(link)}
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}
