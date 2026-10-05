import { Card, Section } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { PublicCourse } from '../lib/load'

export function CoursesIndex({ courses }: { courses: PublicCourse[] }) {
  return (
    <Section eyebrow="Courses" title="CA, CS and CMA" description="Choose a course to explore its levels and papers.">
      <div className="grid gap-5 md:grid-cols-3">
        {courses.map((c) => (
          <Link key={c.slug} to="/courses/$course" params={{ course: c.slug }} className="group block">
            <Card className="h-full p-7 transition-all group-hover:-translate-y-1 group-hover:shadow-lift">
              <span className="font-display text-5xl font-extrabold text-primary">{c.name}</span>
              <h2 className="mt-4 text-lg font-semibold">{c.fullName}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{c.description}</p>
            </Card>
          </Link>
        ))}
      </div>
    </Section>
  )
}
