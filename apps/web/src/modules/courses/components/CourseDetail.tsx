import { Card, ChevronRight, Container } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import type { PublicCourse } from '../lib/load'

export function CourseDetail({ course, prompt }: { course: PublicCourse; prompt?: ReactNode }) {
  return (
    <Container className="py-16 sm:py-24">
      <p className="text-sm font-semibold tracking-widest text-primary uppercase">{course.body}</p>
      <h1 className="mt-2 text-4xl font-extrabold sm:text-5xl">
        {course.fullName} ({course.name})
      </h1>
      <p className="mt-4 max-w-2xl text-lg text-muted-foreground">{course.description}</p>
      {prompt ? <div className="mt-8">{prompt}</div> : null}
      <div className="mt-12 grid gap-5 md:grid-cols-3">
        {course.levels.map((l) => (
          <Link
            key={l.slug}
            to="/courses/$course/$level"
            params={{ course: course.slug, level: l.slug }}
            className="group block"
          >
            <Card className="flex h-full flex-col p-6 transition-all group-hover:-translate-y-1 group-hover:shadow-lift">
              <h2 className="text-xl font-bold">{l.name}</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {l.subjects.length} {l.subjects.length === 1 ? 'paper' : 'papers'}
              </p>
              <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {l.subjects.slice(0, 3).map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
              <p className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-primary">
                Open papers <ChevronRight aria-hidden className="size-4" />
              </p>
            </Card>
          </Link>
        ))}
      </div>
    </Container>
  )
}
