import { Button, Kbd, Search, SidebarMobileTrigger } from '@artha/design-system'
import { Link, useLocation } from '@tanstack/react-router'

import { BellContainer } from '~/modules/notifications'

import { currentSection } from './app-nav'
import { useWorkspaceNav } from './useWorkspaceNav'
import { workspaceIcon } from './workspace-icons'
import type { WorkspaceLink } from './workspace-nav'

const isMac = () => typeof navigator !== 'undefined' && /mac|iphone|ipad/i.test(navigator.platform)

/** 44 px bar above every app page: where you are, a jump-to search, and the notification bell. */
export function AppTopbar({ onSearch }: { onSearch: () => void }) {
  const { study, staff } = useWorkspaceNav()
  const pathname = useLocation({ select: (l) => l.pathname })
  const section = currentSection(pathname, study)
  const Icon =
    section.to.startsWith('/app/') && section.label !== 'Settings'
      ? workspaceIcon(section.to as WorkspaceLink['to'])
      : null
  return (
    <div
      data-slot="app-topbar"
      className="sticky top-0 z-20 flex h-11 shrink-0 items-center gap-2 border-b bg-background/85 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/70 md:px-5"
    >
      <SidebarMobileTrigger className="-ml-1" />
      <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-[13px]">
        <Link
          to={section.to as WorkspaceLink['to']}
          className="flex min-w-0 items-center gap-1.5 font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          {Icon ? <Icon aria-hidden className="size-4 shrink-0 text-muted-foreground" /> : null}
          <span className="truncate">{section.label}</span>
        </Link>
      </nav>
      {staff.length > 0 ? (
        <nav aria-label="Staff" className="ml-3 hidden items-center gap-0.5 border-l pl-3 md:flex">
          {staff.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className="rounded-md px-2 py-1 text-xs font-medium text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 data-[status=active]:bg-muted data-[status=active]:text-foreground"
            >
              {link.label}
            </Link>
          ))}
        </nav>
      ) : null}
      <div className="ml-auto flex items-center gap-1.5">
        <Button
          variant="outline"
          size="sm"
          className="w-9 px-0 text-muted-foreground sm:w-56 sm:justify-start sm:px-2.5"
          onClick={onSearch}
          aria-label="Search and jump to"
          aria-keyshortcuts="Control+K Meta+K"
        >
          <Search aria-hidden />
          <span className="hidden flex-1 text-left sm:inline">Search or jump to…</span>
          <Kbd className="hidden sm:inline-flex">{isMac() ? '⌘K' : 'Ctrl K'}</Kbd>
        </Button>
        <BellContainer />
      </div>
    </div>
  )
}
