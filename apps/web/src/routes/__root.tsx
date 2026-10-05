/// <reference types="vite/client" />
import { buildThemeInitScript, THEME_META_COLORS, ThemeProvider } from '@artha/design-system'
import { type QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createRootRouteWithContext, HeadContent, Outlet, Scripts } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { env } from '~/lib/env'
import { AuthProvider } from '~/modules/auth'
import { LiveMiniTimer } from '~/modules/focus'
import { SiteShell } from '~/modules/layout'
import { ErrorFallback } from '~/modules/layout/ErrorFallback'
import { ObservabilityProvider } from '~/modules/observability'
import { buildHead, organizationJsonLd, websiteJsonLd } from '~/modules/seo'
import appCss from '~/styles.css?url'

// Runs before first paint so there is no theme flash (Reading is the default; System resolves by time of day).
const themeScript = buildThemeInitScript()

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => {
    const base = buildHead({
      title: 'ArthaCommerce: Exam Preparation Workspace for CA, CS and CMA',
      description:
        'Plan your study, track every chapter, practise mock tests and revise smarter. The exam preparation workspace for CA, CS and CMA students in India.',
      path: '/',
      jsonLd: [organizationJsonLd(), websiteJsonLd()],
    })
    return {
      meta: [
        { charSet: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'theme-color', content: THEME_META_COLORS.reading },
        ...base.meta,
      ],
      links: [
        { rel: 'stylesheet', href: appCss },
        { rel: 'icon', href: '/favicon.svg', type: 'image/svg+xml' },
        { rel: 'apple-touch-icon', href: '/icon-512.png' },
        { rel: 'manifest', href: '/manifest.webmanifest' },
        ...base.links,
      ],
      scripts: base.scripts,
    }
  },
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
              <SiteShell>
                <Outlet />
              </SiteShell>
              <LiveMiniTimer />
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
      </head>
      <body data-site={env.VITE_SITE_NAME}>
        {children}
        <Scripts />
      </body>
    </html>
  )
}
