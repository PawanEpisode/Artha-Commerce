import { ArrowRight, Badge, buttonVariants, Card, Container } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import type { PublicCourse } from '../lib/load'

interface Props {
  courses: PublicCourse[]
  /** The student's enrolled course code, lowercased, when they have one. */
  activeCourseCode?: string | null
  prompt?: ReactNode
}

export function CoursesIndex({ courses, activeCourseCode, prompt }: Props) {
  return (
    <Container className="py-12 sm:py-20">
      <header className="max-w-2xl">
        <p className="mb-3 text-sm font-semibold tracking-widest text-primary uppercase">Courses</p>
        <h1 className="text-3xl font-bold sm:text-4xl">CA, CS and CMA</h1>
        <p className="mt-4 text-lg text-muted-foreground">
          Open a course to read its papers and chapters. Tick what you have finished once you are signed in.
        </p>
      </header>
      {prompt ? <div className="mt-10">{prompt}</div> : null}
      <ul className="mt-8 grid list-none gap-5 md:grid-cols-3">
        {courses.map((c) => {
          const papers = c.levels.reduce((sum, level) => sum + level.subjects.length, 0)
          const yours = activeCourseCode === c.slug
          return (
            <li key={c.slug}>
              <Link
                to="/courses/$course"
                params={{ course: c.slug }}
                className="group block h-full rounded-xl outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
              >
                <Card className="flex h-full flex-col p-7 transition-all group-hover:-translate-y-1 group-hover:shadow-lift">
                  <div className="flex items-start justify-between gap-3">
                    <span className="font-display text-5xl font-extrabold text-primary">{c.name}</span>
                    {yours ? <Badge variant="accent">Your course</Badge> : null}
                  </div>
                  <h2 className="mt-4 text-lg font-semibold">{c.fullName}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">{c.tagline}</p>
                  <p className="mt-3 text-sm text-muted-foreground">{c.levels.map((l) => l.name).join(' · ')}</p>
                  {papers > 0 ? (
                    <p className="mt-2 text-sm text-muted-foreground">
                      {papers} {papers === 1 ? 'paper' : 'papers'}
                    </p>
                  ) : null}
                  <span className="mt-auto pt-5">
                    <span className={buttonVariants({ variant: 'outline' })}>
                      Browse {c.name} papers
                      <ArrowRight
                        aria-hidden
                        className="transition-transform group-hover:translate-x-1 motion-reduce:transition-none"
                      />
                    </span>
                  </span>
                </Card>
              </Link>
            </li>
          )
        })}
      </ul>
    </Container>
  )
}
