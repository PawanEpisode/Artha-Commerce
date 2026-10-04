/// <reference types="vite/client" />
import type { ReactNode } from 'react'
import { HeadContent, Outlet, Scripts, createRootRouteWithContext } from '@tanstack/react-router'
import { QueryClientProvider, type QueryClient } from '@tanstack/react-query'
import appCss from '~/design-system/styles.css?url'
import { env } from '~/lib/env'
import { AuthProvider } from '~/modules/auth'
import { ErrorFallback } from '~/modules/layout/ErrorFallback'
import { SiteShell } from '~/modules/layout'
import { ObservabilityProvider } from '~/modules/observability'
import { buildHead, organizationJsonLd, websiteJsonLd } from '~/modules/seo'

// Runs before first paint so there is no light/dark flash.
const themeScript = `try{var t=localStorage.getItem('theme');if(t==='dark'||(!t&&matchMedia('(prefers-color-scheme: dark)').matches))document.documentElement.classList.add('dark')}catch(e){}`

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
        { name: 'theme-color', content: '#4a3fd6' },
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
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ObservabilityProvider>
            <SiteShell>
              <Outlet />
            </SiteShell>
          </ObservabilityProvider>
        </AuthProvider>
      </QueryClientProvider>
    </RootDocument>
  )
}

function RootDocument({ children }: { children: ReactNode }) {
  return (
    <html lang="en-IN" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <HeadContent />
      </head>
      <body data-site={env.VITE_SITE_NAME}>
        {children}
        <Scripts />
      </body>
    </html>
  )
}
