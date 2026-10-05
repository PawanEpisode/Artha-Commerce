import { ArrowRight, Badge, Button, buttonVariants, Card, Container, Skeleton } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import type { PublicCourse } from '../lib/load'
import type { StudyHomeView } from '../lib/visible'

interface Props {
  courses: PublicCourse[]
  view: StudyHomeView
  firstName?: string
  prompt?: ReactNode
}

function paperCount(course: PublicCourse): number {
  return course.levels.reduce((sum, level) => sum + level.subjects.length, 0)
}

function CourseLink({ course }: { course: PublicCourse }) {
  const papers = paperCount(course)
  return (
    <Link
      to="/courses/$course"
      params={{ course: course.slug }}
      className="group block h-full rounded-xl outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
    >
      <Card className="flex h-full flex-col p-7 transition-all group-hover:-translate-y-1 group-hover:shadow-lift">
        <span className="font-display text-5xl font-extrabold text-primary">{course.name}</span>
        <h2 className="mt-4 text-lg font-semibold">{course.fullName}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{course.tagline}</p>
        <p className="mt-3 text-sm text-muted-foreground">{course.levels.map((level) => level.name).join(' · ')}</p>
        {papers > 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">
            {papers} {papers === 1 ? 'paper' : 'papers'}
          </p>
        ) : null}
        <span className="mt-auto pt-5">
          <span className={buttonVariants({ variant: 'outline' })}>
            Browse {course.name} papers
            <ArrowRight
              aria-hidden
              className="transition-transform group-hover:translate-x-1 motion-reduce:transition-none"
            />
          </span>
        </span>
      </Card>
    </Link>
  )
}

/** Signed-in home: a real coverage number, then the one course they are tracking. */
export function StudyHome({ courses, view, firstName, prompt }: Props) {
  const enrolled = view === 'enrolled' ? courses[0] : undefined
  const hello = firstName ? `Welcome back, ${firstName}` : 'Welcome back'
  return (
    <section className="relative overflow-hidden">
      <div aria-hidden className="bg-grid absolute inset-0 -z-10" />
      <Container className="py-12 sm:py-16">
        <header className="max-w-2xl">
          <p className="text-sm font-semibold tracking-widest text-primary uppercase">Your study</p>
          <h1 className="mt-3 text-4xl font-extrabold sm:text-5xl">{hello}</h1>
          <p className="mt-4 text-lg text-muted-foreground">
            {view === 'pending'
              ? 'Loading the course you are tracking.'
              : enrolled
                ? `${enrolled.fullName}. Continue a chapter, or open its papers.`
                : 'Pick CA, CS or CMA. This page keeps the course you are preparing for.'}
          </p>
        </header>
        {view === 'pending' ? (
          <div className="mt-10 grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(16rem,0.8fr)]" aria-busy="true">
            <p className="sr-only">Loading your course</p>
            <Skeleton className="h-40 w-full rounded-xl" />
            <Skeleton className="h-40 w-full rounded-xl" />
          </div>
        ) : (
          <>
            {prompt ? <div className="mt-10">{prompt}</div> : null}
            {enrolled ? (
              <Card className="mt-5 flex flex-col gap-6 p-7 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="font-display text-5xl font-extrabold text-primary">{enrolled.name}</span>
                    <Badge variant="accent">Your course</Badge>
                  </div>
                  <h2 className="mt-4 text-lg font-semibold">{enrolled.fullName}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">{enrolled.tagline}</p>
                  <p className="mt-3 text-sm text-muted-foreground">
                    {enrolled.levels.map((level) => level.name).join(' · ')}
                  </p>
                </div>
                <Button variant="outline" arrow className="w-full shrink-0 sm:w-auto" asChild>
                  <Link to="/courses/$course" params={{ course: enrolled.slug }}>
                    Browse {enrolled.name} papers
                  </Link>
                </Button>
              </Card>
            ) : (
              <ul className="mt-8 grid list-none gap-5 md:grid-cols-3">
                {courses.map((course) => (
                  <li key={course.slug}>
                    <CourseLink course={course} />
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Container>
    </section>
  )
}
