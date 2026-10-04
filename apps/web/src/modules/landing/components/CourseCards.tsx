import { Link } from '@tanstack/react-router'
import { ArrowUpRight } from 'lucide-react'
import { Card } from '~/components/ui/card'
import { Reveal, Section } from '~/design-system'
import { courses } from '~/modules/catalog'

export function CourseCards() {
  return (
    <Section eyebrow="Courses" title="Pick your path" description="Every level of every course, in one place.">
      <div className="grid gap-5 md:grid-cols-3">
        {courses.map((c, i) => (
          <Reveal key={c.slug} delay={i * 0.08}>
            <Link to="/courses/$course" params={{ course: c.slug }} className="group block h-full">
              <Card className="h-full p-7 transition-all group-hover:-translate-y-1 group-hover:shadow-lift">
                <div className="flex items-start justify-between">
                  <span className="font-display text-5xl font-extrabold text-primary">{c.name}</span>
                  <ArrowUpRight className="text-muted-foreground transition-colors group-hover:text-primary" />
                </div>
                <h3 className="mt-4 text-lg font-semibold">{c.fullName}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{c.tagline}</p>
                <p className="mt-5 text-xs font-medium text-muted-foreground">
                  {c.body} · {c.levels.map((l) => l.name).join(' · ')}
                </p>
              </Card>
            </Link>
          </Reveal>
        ))}
      </div>
    </Section>
  )
}
