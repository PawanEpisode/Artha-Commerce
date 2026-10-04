import {
  ArrowRight,
  Badge,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
  Button,
  Card,
  Container,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { marksLabel, pluralize } from '../lib/format'
import type { SubjectSyllabus } from '../lib/types'
import { SyllabusMeta } from './SyllabusMeta'

interface Props {
  courseName: string
  levelName: string
  body: string
  subject: SubjectSyllabus
  /** The "Report a wrong item" control. */
  report?: ReactNode
}

export function SubjectView({ courseName, levelName, body, subject, report }: Props) {
  const course = subject.course
  const level = subject.level
  return (
    <Container className="max-w-3xl py-12 sm:py-20">
      <Breadcrumb className="mb-6">
        <BreadcrumbList>
          <BreadcrumbItem>
            <Link to="/courses/$course" params={{ course }} className="underline-offset-4 hover:underline">
              {courseName}
            </Link>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <Link
              to="/courses/$course/$level"
              params={{ course, level }}
              className="underline-offset-4 hover:underline"
            >
              {levelName}
            </Link>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{subject.name}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <h1 className="text-4xl font-extrabold sm:text-5xl">{subject.name}</h1>
      <p className="mt-3 flex flex-wrap items-center gap-2 text-lg text-muted-foreground">
        {subject.paper_number ? <span>Paper {subject.paper_number}</span> : null}
        {subject.total_marks ? <Badge variant="outline">{subject.total_marks} marks</Badge> : null}
        {subject.is_optional ? <Badge variant="outline">Optional</Badge> : null}
        {subject.chapters.length > 0 ? <span>{pluralize(subject.chapters.length, 'chapter')}</span> : null}
      </p>
      <div className="mt-3">
        <SyllabusMeta scheme={subject.scheme} body={body} />
      </div>

      {subject.chapters.length === 0 ? (
        <p className="mt-10 rounded-xl border border-dashed p-6 text-muted-foreground">
          The chapter list for this paper is coming soon.
        </p>
      ) : (
        <ol className="mt-10 space-y-3">
          {subject.chapters.map((c, i) => (
            <li key={c.id}>
              <Card className="focus-within:ring-[3px] focus-within:ring-ring/40 hover:shadow-(--shadow-soft)">
                <Link
                  to="/courses/$course/$level/$subject/$chapter"
                  params={{ course, level, subject: subject.key, chapter: c.key }}
                  className="flex items-center gap-4 rounded-xl p-4 outline-none"
                >
                  <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-secondary font-display font-bold text-primary">
                    {i + 1}
                  </span>
                  <span className="min-w-0 flex-1 font-medium">{c.name}</span>
                  {marksLabel(c) ? <Badge variant="outline">{marksLabel(c)}</Badge> : null}
                </Link>
              </Card>
            </li>
          ))}
        </ol>
      )}

      <div className="mt-10 flex flex-wrap items-center gap-3">
        <Button size="lg" asChild>
          <Link to="/app/syllabus">
            Track {subject.name} <ArrowRight />
          </Link>
        </Button>
        {report}
      </div>
    </Container>
  )
}
