import {
  Button,
  Container,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Logo,
  LogOut,
  Menu,
  ThemeSwitcher,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useEffect } from 'react'

import { useAuth } from '~/modules/auth'
import { BellContainer } from '~/modules/notifications'
import { IdentityAvatar, useBootstrap } from '~/modules/personalization'

import { mainNav } from './main-nav'
import { useWorkspaceNav } from './useWorkspaceNav'
import { workspaceIcon } from './workspace-icons'
import type { WorkspaceLink } from './workspace-nav'

function MenuLinks({ links }: { links: readonly WorkspaceLink[] }) {
  return links.map((item) => {
    const Icon = workspaceIcon(item.to)
    return (
      <DropdownMenuItem key={item.to} asChild>
        <Link to={item.to}>
          <Icon aria-hidden />
          {item.label}
        </Link>
      </DropdownMenuItem>
    )
  })
}

function AccountMenu({ email, onSignOut }: { email?: string; onSignOut: () => void }) {
  const { study, settings } = useWorkspaceNav()
  const { data } = useBootstrap()
  const firstName = data?.first_name
  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        {/* The 44 px target is the whole button; the first name is hidden under 640 px so nothing overflows at 320. */}
        <Button variant="ghost" className="h-11 min-w-11 gap-2 rounded-full px-1 sm:pr-3" aria-label="Account menu">
          <IdentityAvatar size={32} decorative />
          {firstName ? <span className="hidden max-w-28 truncate sm:inline">{firstName}</span> : null}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        {data?.full_name ? (
          <DropdownMenuLabel className="tracking-normal normal-case">
            <span className="block max-w-56 truncate text-foreground">{data.full_name}</span>
            {email ? <span className="block max-w-56 truncate font-normal">{email}</span> : null}
          </DropdownMenuLabel>
        ) : email ? (
          <DropdownMenuLabel className="tracking-normal break-all normal-case">{email}</DropdownMenuLabel>
        ) : null}
        <DropdownMenuItem asChild>
          <Link to="/app">Workspace</Link>
        </DropdownMenuItem>
        {study.length > 0 ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Study</DropdownMenuLabel>
            <MenuLinks links={study} />
          </>
        ) : null}
        <DropdownMenuSeparator />
        <DropdownMenuLabel>Settings</DropdownMenuLabel>
        <MenuLinks links={settings} />
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onSignOut}>
          <LogOut aria-hidden /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function SiteHeader() {
  const { user, loading, signOut } = useAuth()
  const signedIn = !loading && Boolean(user)
  const links = mainNav(signedIn)
  // The head script hides guest-only chrome before paint. Drop that mark if the session is not real.
  useEffect(() => {
    if (loading) return
    if (user) document.documentElement.dataset.signedIn = '1'
    else delete document.documentElement.dataset.signedIn
  }, [loading, user])
  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur-xl">
      <style>{`html[data-signed-in="1"] [data-nav="courses"]{display:none}`}</style>
      <Container className="flex h-[var(--site-header-height)] items-center justify-between gap-2">
        <Link to="/" aria-label="ArthaCommerce home" className="shrink-0">
          <Logo compactOnMobile />
        </Link>
        <div className="flex min-w-0 items-center gap-1 sm:gap-2">
          <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
            {links.map((item) => (
              <Button
                key={item.to}
                variant="ghost"
                size="sm"
                data-nav={item.to === '/courses' ? 'courses' : undefined}
                asChild
              >
                <Link to={item.to} activeProps={{ className: 'text-primary' }}>
                  {item.label}
                </Link>
              </Button>
            ))}
          </nav>
          <ThemeSwitcher />
          {signedIn ? (
            <>
              <Button size="sm" className="hidden sm:inline-flex" asChild>
                <Link to="/app">Open workspace</Link>
              </Button>
              <BellContainer />
              <AccountMenu email={user?.email} onSignOut={() => void signOut()} />
            </>
          ) : (
            <Button size="sm" asChild>
              <Link to="/login">Start free</Link>
            </Button>
          )}
          <DropdownMenu modal={false}>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu">
                <Menu />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="md:hidden">
              {links.map((item) => (
                <DropdownMenuItem key={item.to} data-nav={item.to === '/courses' ? 'courses' : undefined} asChild>
                  <Link to={item.to}>{item.label}</Link>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </Container>
    </header>
  )
}
