import { Link } from '@tanstack/react-router'
import { Container, Logo } from '~/design-system'
import { courses, features } from '~/modules/catalog'

export function SiteFooter() {
  return (
    <footer className="border-t bg-muted/40">
      <Container className="grid gap-10 py-14 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-3">
          <Logo />
          <p className="max-w-xs text-sm text-muted-foreground">
            The exam preparation workspace for CA, CS and CMA students in India.
          </p>
        </div>
        <nav aria-label="Courses" className="space-y-3 text-sm">
          <p className="font-semibold">Courses</p>
          {courses.map((c) => (
            <Link key={c.slug} to="/courses/$course" params={{ course: c.slug }} className="block text-muted-foreground hover:text-foreground">
              {c.name} ({c.body})
            </Link>
          ))}
        </nav>
        <nav aria-label="Features" className="space-y-3 text-sm">
          <p className="font-semibold">Features</p>
          {features.slice(0, 5).map((f) => (
            <Link key={f.slug} to="/features/$slug" params={{ slug: f.slug }} className="block text-muted-foreground hover:text-foreground">
              {f.title}
            </Link>
          ))}
        </nav>
        <div className="space-y-3 text-sm">
          <p className="font-semibold">Disclaimer</p>
          <p className="text-muted-foreground">
            ArthaCommerce is an independent study platform and is not affiliated with ICAI, ICSI or ICMAI.
          </p>
        </div>
      </Container>
      <div className="border-t py-5 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} ArthaCommerce. All rights reserved.
      </div>
    </footer>
  )
}
