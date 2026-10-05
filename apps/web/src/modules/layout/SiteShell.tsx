import type { CSSProperties, ReactNode } from 'react'

import { SiteFooter } from './SiteFooter'
import { SiteHeader } from './SiteHeader'

export function SiteShell({ children }: { children: ReactNode }) {
  return (
    // Sticky bars below the header (SectionTabs) read this var; the header is h-16 at every width.
    <div className="flex min-h-dvh flex-col" style={{ '--site-header-height': '4rem' } as CSSProperties}>
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
      <SiteFooter />
    </div>
  )
}
