import { useMatches } from '@tanstack/react-router'
import { type CSSProperties, type ReactNode, useEffect, useState } from 'react'

import { useAuth } from '~/modules/auth'

import { AppShell } from './AppShell'
import { hasFooter, isAppChrome, isBareChrome } from './chrome'
import { SiteFooter } from './SiteFooter'
import { SiteHeader } from './SiteHeader'

/**
 * A signed-in student on a static public page (home, courses, features) sees the same frame as the rest of the app:
 * sidebar, topbar, full-width page. Signed-out visitors keep the public header and footer. The first client render
 * matches the server (public chrome); a stored-session mark set before paint hides the public header meanwhile, so
 * there is no flash of marketing chrome.
 */
function useMemberFrame(eligible: boolean): boolean {
  const { user, loading } = useAuth()
  const [hydrated, setHydrated] = useState(false)
  useEffect(() => setHydrated(true), [])
  if (!eligible || !hydrated) return false
  if (user) return true
  return loading && document.documentElement.dataset.signedIn === '1'
}

export function SiteShell({ children }: { children: ReactNode }) {
  const bare = useMatches({ select: isBareChrome })
  const app = useMatches({ select: isAppChrome })
  const footer = useMatches({ select: hasFooter })
  const member = useMemberFrame(footer)
  // A page in its own small window (the fallback timer) has no header, footer or skip link.
  if (bare) return <main id="main">{children}</main>
  // The signed-in app draws its own frame (sidebar, topbar, skip link, main landmark) in the /app layout route.
  if (app) return <>{children}</>
  if (member) return <AppShell>{children}</AppShell>
  // Otherwise the footer shows only on routes that ask for it (see `chrome.ts`).
  return (
    // Sticky bars below the header (SectionTabs) read this var; the public header is h-12 at every width.
    <div className="flex min-h-dvh flex-col" style={{ '--site-header-height': '3rem' } as CSSProperties}>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        Skip to content
      </a>
      <SiteHeader />
      <main id="main" className="flex-1">
        {children}
      </main>
      {footer ? <SiteFooter /> : null}
    </div>
  )
}
