/// <reference types="vite/client" />
import { buildThemeInitScript, THEME_META_COLORS, ThemeProvider, Toaster } from '@artha/design-system'
import { type QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createRootRouteWithContext, HeadContent, Outlet, Scripts } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { env } from '~/lib/env'
import { AuthProvider } from '~/modules/auth'
import { LiveMiniTimer } from '~/modules/focus'
import { SIGNED_IN_MARK_SCRIPT, SiteShell } from '~/modules/layout'
import { ErrorFallback } from '~/modules/layout/ErrorFallback'
import { NotificationsBoot } from '~/modules/notifications'
import { ObservabilityProvider } from '~/modules/observability'
import { PersonalizedPostAuth } from '~/modules/personalization'
import appCss from '~/styles.css?url'

// Runs before first paint so there is no theme flash (Reading is the default; System resolves by time of day).
const themeScript = buildThemeInitScript()

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  // Document-level tags only. Titles, descriptions, Open Graph, canonical and JSON-LD belong to each route
  // (`head: () => pageHead(...)`), so a child can never inherit another page's preview.
  head: () => ({
    meta: [
      { charSet: 'utf-8' },
      { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      { name: 'theme-color', content: THEME_META_COLORS.reading },
    ],
    links: [
      { rel: 'stylesheet', href: appCss },
      { rel: 'icon', href: '/favicon.svg', type: 'image/svg+xml' },
      { rel: 'apple-touch-icon', href: '/icon-512.png' },
      { rel: 'manifest', href: '/manifest.webmanifest' },
    ],
  }),
  component: RootComponent,
  errorComponent: ({ error, reset }) => (
    <RootDocument>
      <ErrorFallback error={error as Error} reset={reset} />
    </RootDocument>
  ),
})

function RootComponent() {
  const { queryClient } = Route.useRouteContext()
  return (
    <RootDocument>
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <ObservabilityProvider>
              <PersonalizedPostAuth>
                <SiteShell>
                  <Outlet />
                </SiteShell>
                <LiveMiniTimer />
                <NotificationsBoot />
                {/* The one toaster for the whole app. Modules only call `toast.*` / their own `notify`. */}
                <Toaster />
              </PersonalizedPostAuth>
            </ObservabilityProvider>
          </AuthProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </RootDocument>
  )
}

function RootDocument({ children }: { children: ReactNode }) {
  return (
    <html lang="en-IN" data-theme="reading" suppressHydrationWarning>
      <head>
        <HeadContent />
        {/* After the stylesheet link and the theme-color meta, before first paint. */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <script dangerouslySetInnerHTML={{ __html: SIGNED_IN_MARK_SCRIPT }} />
      </head>
      <body data-site={env.VITE_SITE_NAME}>
        {children}
        <Scripts />
      </body>
    </html>
  )
}
