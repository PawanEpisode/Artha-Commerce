import {
  AppFrameContext,
  type CommandItem,
  CommandPalette,
  GraduationCap,
  isThemePreference,
  LogOut,
  PanelLeft,
  Settings,
  SidebarInset,
  SidebarProvider,
  Sparkles,
  THEME_OPTIONS,
  useSidebar,
  useTheme,
} from '@artha/design-system'
import { useLocation, useMatches, useNavigate } from '@tanstack/react-router'
import { type CSSProperties, type ReactNode, useCallback, useEffect, useMemo, useState } from 'react'

import { useAuth } from '~/modules/auth'

import { isSettingsPath } from './app-nav'
import { AppSidebar } from './AppSidebar'
import { AppTopbar } from './AppTopbar'
import { isBareChrome } from './chrome'
import { SettingsFrame } from './SettingsFrame'
import { useWorkspaceNav } from './useWorkspaceNav'
import { workspaceIcon } from './workspace-icons'
import { NAV_GROUPS, type WorkspaceLink, type WorkspaceSubLink } from './workspace-nav'

/** Cmd/Ctrl+K palette: every destination, plus the few actions people look for. Built from the same flag-filtered links as the sidebar. */
function CommandMenu({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { study, settings, staff } = useWorkspaceNav()
  const navigate = useNavigate()
  const { signOut } = useAuth()
  const { setPreference } = useTheme()
  const { toggle } = useSidebar()

  const items = useMemo<CommandItem[]>(() => {
    const groupLabel = (link: WorkspaceLink) => NAV_GROUPS.find((g) => g.id === link.group)?.label ?? 'Go to'
    return [
      {
        id: '/app',
        label: 'Home',
        group: 'Go to',
        icon: workspaceIcon('/app/today'),
        keywords: ['dashboard', 'workspace'],
      },
      ...study.flatMap((l) => [
        {
          id: l.to,
          label: l.label,
          group: groupLabel(l),
          icon: workspaceIcon(l.to),
          keywords: l.description?.split(' '),
        },
        ...(l.children ?? []).map((child) => ({
          id: child.to,
          label: `${l.label}: ${child.label}`,
          group: groupLabel(l),
          icon: workspaceIcon(l.to),
        })),
      ]),
      ...staff.map((l) => ({ id: l.to, label: l.label, group: 'Staff', icon: Settings })),
      { id: '/courses', label: 'Courses', group: 'Explore', icon: GraduationCap },
      { id: '/features', label: 'Features', group: 'Explore', icon: Sparkles },
      ...settings.map((l) => ({ id: l.to, label: l.label, group: 'Settings', icon: workspaceIcon(l.to) })),
      { id: 'action:sidebar', label: 'Toggle sidebar', group: 'Actions', icon: PanelLeft, hint: '[' },
      ...THEME_OPTIONS.map((t) => ({
        id: `action:theme:${t.value}`,
        label: `Theme: ${t.label}`,
        group: 'Actions',
        icon: t.icon,
      })),
      { id: 'action:signout', label: 'Sign out', group: 'Actions', icon: LogOut },
    ]
  }, [study, settings, staff])

  const onSelect = useCallback(
    (item: CommandItem) => {
      if (item.id.startsWith('/')) void navigate({ to: item.id as WorkspaceLink['to'] | WorkspaceSubLink['to'] })
      else if (item.id === 'action:sidebar') toggle()
      else if (item.id === 'action:signout') void signOut()
      else if (item.id.startsWith('action:theme:')) {
        const value = item.id.slice('action:theme:'.length)
        if (isThemePreference(value)) setPreference(value)
      }
    },
    [navigate, signOut, setPreference, toggle],
  )

  return <CommandPalette open={open} onOpenChange={onOpenChange} items={items} onSelect={onSelect} />
}

/**
 * The signed-in frame: a collapsible sidebar on the left, a slim topbar, and the page using the full remaining width.
 * Rendered by the /app layout route. A bare child route (the pop-out timer, the PDF reader) gets no frame at all.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const bare = useMatches({ select: isBareChrome })
  const pathname = useLocation({ select: (l) => l.pathname })
  const [paletteOpen, setPaletteOpen] = useState(false)

  // Dialogs and menus render in a portal under <body>; mark it so they get the app's density too.
  useEffect(() => {
    if (bare) return
    document.body.setAttribute('data-app-frame', '')
    return () => document.body.removeAttribute('data-app-frame')
  }, [bare])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPaletteOpen((open) => !open)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  if (bare) return <>{children}</>

  // First-run onboarding is a focused flow: no navigation to wander off into.
  const focused = pathname.replace(/\/+$/, '').startsWith('/app/onboarding')

  return (
    <AppFrameContext.Provider value>
      <SidebarProvider>
        <div
          data-app-frame
          className="flex min-h-dvh bg-background text-foreground"
          // SectionTabs and other sticky bars stick under the 44 px topbar.
          style={{ '--site-header-height': '2.75rem' } as CSSProperties}
        >
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-1.5 focus:text-primary-foreground"
          >
            Skip to content
          </a>
          {focused ? null : <AppSidebar />}
          <SidebarInset>
            <AppTopbar onSearch={() => setPaletteOpen(true)} />
            <main id="main" className="min-w-0 flex-1">
              {isSettingsPath(pathname) ? <SettingsFrame>{children}</SettingsFrame> : children}
            </main>
          </SidebarInset>
        </div>
        <CommandMenu open={paletteOpen} onOpenChange={setPaletteOpen} />
      </SidebarProvider>
    </AppFrameContext.Provider>
  )
}
