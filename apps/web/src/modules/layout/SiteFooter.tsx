import { Container, Logo } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { courses, features } from '~/modules/catalog'

export function SiteFooter() {
  return (
    <>
      {/* The head script marks a stored session before first paint, so a signed-in student never sees the footer flash. */}
      <style>{`html[data-signed-in="1"] [data-slot="site-footer"]{display:none}`}</style>
      <footer data-slot="site-footer" className="border-t bg-muted/40">
        <Container className="grid gap-6 py-8 sm:grid-cols-2 sm:py-10 lg:grid-cols-4">
          <div className="space-y-2">
            <Logo />
            <p className="max-w-xs text-[13px] text-muted-foreground">
              The exam preparation workspace for CA, CS and CMA students in India.
            </p>
          </div>
          <nav aria-label="Courses" className="space-y-1.5 text-[13px]">
            <p className="font-semibold">Courses</p>
            {courses.map((c) => (
              <Link
                key={c.slug}
                to="/courses/$course"
                params={{ course: c.slug }}
                className="block text-muted-foreground hover:text-foreground"
              >
                {c.name} ({c.body})
              </Link>
            ))}
          </nav>
          <nav aria-label="Features" className="space-y-1.5 text-[13px]">
            <p className="font-semibold">Features</p>
            {features.slice(0, 5).map((f) => (
              <Link
                key={f.slug}
                to="/features/$slug"
                params={{ slug: f.slug }}
                className="block text-muted-foreground hover:text-foreground"
              >
                {f.title}
              </Link>
            ))}
          </nav>
          <div className="space-y-1.5 text-[13px]">
            <p className="font-semibold">Disclaimer</p>
            <p className="text-muted-foreground">
              ArthaCommerce is an independent study platform and is not affiliated with ICAI, ICSI or ICMAI.
            </p>
          </div>
        </Container>
        <div className="border-t py-3 text-center text-xs text-muted-foreground">
          © {new Date().getFullYear()} ArthaCommerce. All rights reserved.
        </div>
      </footer>
    </>
  )
}
