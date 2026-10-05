import { ArrowRight, buttonVariants, Card, Reveal, Section } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { courses } from '~/modules/catalog'

export function CourseCards() {
  return (
    <Section eyebrow="Courses" title="Pick your path" description="Every level of every course, in one place.">
      <div className="grid gap-5 md:grid-cols-3">
        {courses.map((c, i) => (
          <Reveal key={c.slug} delay={i * 0.08}>
            <Link
              to="/courses/$course"
              params={{ course: c.slug }}
              className="group block h-full rounded-xl outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
            >
              <Card className="flex h-full flex-col p-7 transition-all group-hover:-translate-y-1 group-hover:shadow-lift">
                <span className="font-display text-5xl font-extrabold text-primary">{c.name}</span>
                <h3 className="mt-4 text-lg font-semibold">{c.fullName}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{c.tagline}</p>
                <p className="mt-5 text-xs font-medium text-muted-foreground">
                  {c.body} · {c.levels.map((l) => l.name).join(' · ')}
                </p>
                <span className="mt-5 block">
                  <span className={buttonVariants({ variant: 'outline', size: 'sm' })}>
                    Explore {c.name}
                    <ArrowRight
                      aria-hidden
                      className="transition-transform group-hover:translate-x-1 motion-reduce:transition-none"
                    />
                  </span>
                </span>
              </Card>
            </Link>
          </Reveal>
        ))}
      </div>
    </Section>
  )
}
