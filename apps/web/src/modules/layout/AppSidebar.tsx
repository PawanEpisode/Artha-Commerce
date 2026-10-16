import {
  ChevronsUpDown,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  GraduationCap,
  House,
  isThemePreference,
  LogoMark,
  LogOut,
  Settings,
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarHeader,
  SidebarItem,
  sidebarItemClass,
  Sparkles,
  THEME_OPTIONS,
  Tooltip,
  TooltipProvider,
  useSidebar,
  useTheme,
} from '@artha/design-system'
import { Link, useLocation } from '@tanstack/react-router'

import { useAuth } from '~/modules/auth'
import { IdentityAvatar, useBootstrap } from '~/modules/personalization'

import { isSettingsPath } from './app-nav'
import { useWorkspaceNav } from './useWorkspaceNav'
import { workspaceIcon } from './workspace-icons'
import { NAV_GROUPS } from './workspace-nav'

function UserMenu() {
  const { user, signOut } = useAuth()
  const { data } = useBootstrap()
  const { preference, setPreference } = useTheme()
  const { holdPeek } = useSidebar()
  const name = data?.full_name || data?.first_name || user?.email || 'Account'
  return (
    <DropdownMenu modal={false} onOpenChange={holdPeek}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={`${sidebarItemClass} h-9 pointer-coarse:h-11`}
          aria-label={`Account menu, ${name}`}
        >
          <IdentityAvatar size={24} decorative />
          <span className="min-w-0 flex-1 truncate text-foreground">{name}</span>
          <ChevronsUpDown aria-hidden className="ml-auto size-3.5 rail:hidden" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="right" align="end" sideOffset={10} className="w-60">
        <DropdownMenuLabel className="tracking-normal normal-case">
          <span className="block truncate text-[13px] font-medium text-foreground">{data?.full_name ?? name}</span>
          {user?.email ? <span className="block truncate font-normal">{user.email}</span> : null}
        </DropdownMenuLabel>
        <DropdownMenuItem asChild>
          <Link to="/app/account">
            <Settings aria-hidden /> Account and settings
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <div className="flex items-center justify-between gap-2 px-2.5 py-1">
          <span id="theme-label" className="text-[13px]">
            Theme
          </span>
          <TooltipProvider delayDuration={150}>
            <DropdownMenuRadioGroup
              aria-labelledby="theme-label"
              value={preference}
              onValueChange={(v) => {
                if (isThemePreference(v)) setPreference(v)
              }}
              className="flex gap-0.5 rounded-md bg-muted p-0.5"
            >
              {THEME_OPTIONS.map(({ value, label, icon: Icon }) => (
                <Tooltip key={value} content={label} side="top">
                  <DropdownMenuRadioItem
                    value={value}
                    aria-label={label}
                    // Pick without closing the menu, so the change is seen at once.
                    onSelect={(event) => event.preventDefault()}
                    className="size-7 min-h-0 justify-center rounded p-0 data-[state=checked]:bg-card data-[state=checked]:text-primary data-[state=checked]:shadow-soft pointer-coarse:size-10 pointer-coarse:min-h-0"
                  >
                    <Icon aria-hidden />
                  </DropdownMenuRadioItem>
                </Tooltip>
              ))}
            </DropdownMenuRadioGroup>
          </TooltipProvider>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-destructive" onSelect={() => void signOut()}>
          <LogOut aria-hidden /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** The workspace navigation: every study tool one click away, grouped, with settings and the account at the foot. */
export function AppSidebar() {
  const { study } = useWorkspaceNav()
  const pathname = useLocation({ select: (l) => l.pathname })
  return (
    <Sidebar label="Workspace">
      <SidebarHeader>
        <Link
          to="/app"
          aria-label="ArthaCommerce workspace home"
          className="flex h-8 min-w-0 items-center gap-2.5 rounded-md px-2 whitespace-nowrap outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          <LogoMark className="size-5 shrink-0" />
          <span className="truncate text-sm font-semibold tracking-tight rail:hidden">
            Artha<span className="text-primary">Commerce</span>
          </span>
        </Link>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarItem asChild icon={House}>
            <Link to="/app" activeOptions={{ exact: true }}>
              Home
            </Link>
          </SidebarItem>
        </SidebarGroup>
        {NAV_GROUPS.map((group) => {
          const items = study.filter((link) => link.group === group.id)
          if (items.length === 0) return null
          return (
            <SidebarGroup key={group.id} label={group.label}>
              {items.map((link) => (
                <SidebarItem key={link.to} asChild icon={workspaceIcon(link.to)}>
                  <Link to={link.to}>{link.label}</Link>
                </SidebarItem>
              ))}
            </SidebarGroup>
          )
        })}
        <SidebarGroup label="Explore">
          <SidebarItem asChild icon={GraduationCap}>
            <Link to="/courses">Courses</Link>
          </SidebarItem>
          <SidebarItem asChild icon={Sparkles}>
            <Link to="/features">Features</Link>
          </SidebarItem>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <SidebarItem asChild icon={Settings} data-active={isSettingsPath(pathname)}>
          <Link to="/app/account" activeOptions={{ exact: true }}>
            Settings
          </Link>
        </SidebarItem>
        <UserMenu />
      </SidebarFooter>
    </Sidebar>
  )
}
