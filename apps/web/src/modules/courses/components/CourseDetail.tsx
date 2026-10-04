import { Button, Card, Container } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { Course } from '~/modules/catalog'

export function CourseDetail({ course }: { course: Course }) {
  return (
    <Container className="py-16 sm:py-24">
      <p className="text-sm font-semibold tracking-widest text-primary uppercase">{course.body}</p>
      <h1 className="mt-2 text-4xl font-extrabold sm:text-5xl">
        {course.fullName} ({course.name})
      </h1>
      <p className="mt-4 max-w-2xl text-lg text-muted-foreground">{course.description}</p>
      <div className="mt-12 grid gap-5 md:grid-cols-3">
        {course.levels.map((l) => (
          <Link
            key={l.slug}
            to="/courses/$course/$level"
            params={{ course: course.slug, level: l.slug }}
            className="group block"
          >
            <Card className="h-full p-6 transition-all group-hover:-translate-y-1 group-hover:shadow-lift">
              <h2 className="text-xl font-bold">{l.name}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{l.subjects.length} papers</p>
              <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {l.subjects.slice(0, 3).map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </Card>
          </Link>
        ))}
      </div>
      <Button size="lg" className="mt-12" asChild>
        <Link to="/login">Start preparing for {course.name}</Link>
      </Button>
    </Container>
  )
}
