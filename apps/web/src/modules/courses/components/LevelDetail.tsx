import { ArrowLeft, Button, Container, EntityBadge } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import type { Level } from '~/modules/catalog'
import { EntityIndex, EntityListRow, EntityTitle } from '~/modules/syllabus'

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
    <Container className="py-6 sm:py-8">
      <Button variant="outline" size="sm" className="mb-4" asChild>
        <Link to="/courses/$course" params={{ course: course.slug }}>
          <ArrowLeft /> {course.name}
        </Link>
      </Button>
      <h1 className="text-xl font-semibold tracking-tight">
        {course.name} {level.name}
      </h1>
      <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
        <EntityBadge kind="paper">
          {count} {count === 1 ? 'paper' : 'papers'}
        </EntityBadge>
        {syllabus
          ? 'Open a paper to see its chapters and weightage.'
          : `Syllabus shown is indicative; confirm the current scheme with ${course.body}.`}
      </p>
      {meta ? <div className="mt-2">{meta}</div> : null}
      {prompt ? <div className="mt-4">{prompt}</div> : null}
      {syllabus ? (
        <div className="mt-4">{syllabus}</div>
      ) : (
        <ol className="mt-4 list-none space-y-1.5">
          {level.subjects.map((s, i) => (
            <li key={s}>
              <EntityListRow kind="paper" className="flex items-center gap-3 p-3">
                <EntityIndex kind="paper">{i + 1}</EntityIndex>
                <EntityTitle className="min-w-0 flex-1 font-medium">{s}</EntityTitle>
              </EntityListRow>
            </li>
          ))}
        </ol>
      )}
      {report ? <div className="mt-4">{report}</div> : null}
    </Container>
  )
}
