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
  UserRound,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { useAuth } from '~/modules/auth'

import { useWorkspaceNav } from './useWorkspaceNav'
import { workspaceIcon } from './workspace-icons'
import type { WorkspaceLink } from './workspace-nav'

const nav = [
  { to: '/features', label: 'Features' },
  { to: '/courses', label: 'Courses' },
] as const

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
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Account menu">
          <UserRound />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        {email && <DropdownMenuLabel className="tracking-normal break-all normal-case">{email}</DropdownMenuLabel>}
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
  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur-xl">
      <Container className="flex h-[var(--site-header-height)] items-center justify-between gap-2">
        <Link to="/" aria-label="ArthaCommerce home" className="shrink-0">
          <Logo compactOnMobile />
        </Link>
        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
          {nav.map((item) => (
            <Button key={item.to} variant="ghost" size="sm" asChild>
              <Link to={item.to} activeProps={{ className: 'text-primary' }}>
                {item.label}
              </Link>
            </Button>
          ))}
        </nav>
        <div className="flex items-center gap-1 sm:gap-2">
          <ThemeSwitcher />
          {signedIn ? (
            <>
              <Button size="sm" className="hidden sm:inline-flex" asChild>
                <Link to="/app">Open workspace</Link>
              </Button>
              <AccountMenu email={user?.email} onSignOut={() => void signOut()} />
            </>
          ) : (
            <Button size="sm" asChild>
              <Link to="/login">Start free</Link>
            </Button>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu">
                <Menu />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="md:hidden">
              {nav.map((item) => (
                <DropdownMenuItem key={item.to} asChild>
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
