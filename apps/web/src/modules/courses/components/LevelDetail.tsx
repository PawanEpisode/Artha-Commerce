import { ArrowLeft, Button, Card, Container } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import type { Level } from '~/modules/catalog'

import type { PublicCourse } from '../lib/load'

interface Props {
  course: PublicCourse
  level: Level
  /** The curated syllabus (grouped papers). When absent, the indicative static list is shown. */
  syllabus?: ReactNode
  /** Paper count from the curated syllabus, when there is one. */
  subjectCount?: number
  /** Scheme name and source, shown under the intro. */
  meta?: ReactNode
  /** "Report a wrong item" control, shown under the papers when there is a curated syllabus. */
  report?: ReactNode
  /** Next step: track this level, or continue coverage the student already has. */
  prompt?: ReactNode
}

export function LevelDetail({ course, level, syllabus, subjectCount, meta, report, prompt }: Props) {
  const count = subjectCount ?? level.subjects.length
  return (
    <Container className="max-w-3xl py-16 sm:py-24">
      <Button variant="link" className="mb-6 px-0" asChild>
        <Link to="/courses/$course" params={{ course: course.slug }}>
          <ArrowLeft /> {course.name}
        </Link>
      </Button>
      <h1 className="text-4xl font-extrabold sm:text-5xl">
        {course.name} {level.name}
      </h1>
      <p className="mt-3 text-lg text-muted-foreground">
        {count} papers.{' '}
        {syllabus
          ? 'Open a paper to see its chapters and weightage.'
          : `Syllabus shown is indicative; confirm the current scheme with ${course.body}.`}
      </p>
      {meta ? <div className="mt-3">{meta}</div> : null}
      {prompt ? <div className="mt-8">{prompt}</div> : null}
      {syllabus ? (
        <div className="mt-10">{syllabus}</div>
      ) : (
        <ol className="mt-10 space-y-3">
          {level.subjects.map((s, i) => (
            <Card key={s} className="flex items-center gap-4 p-4">
              <span className="grid size-9 place-items-center rounded-lg bg-secondary font-display font-bold text-primary">
                {i + 1}
              </span>
              <span className="font-medium">{s}</span>
            </Card>
          ))}
        </ol>
      )}
      {report ? <div className="mt-8">{report}</div> : null}
    </Container>
  )
}
