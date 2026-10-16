import {
  ArrowLeft,
  ArrowRight,
  Badge,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
  Button,
  Container,
  EntityBadge,
  EntityDot,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { marksLabel, pluralize } from '../lib/format'
import type { ChapterSyllabus } from '../lib/types'
import { CRUMB_LINK_CLASS, EntityCrumb, EntityListRow, EntityTitle } from './EntityList'

interface Props {
  courseName: string
  levelName: string
  chapter: ChapterSyllabus
  report?: ReactNode
}

export function ChapterView({ courseName, levelName, chapter, report }: Props) {
  const { course, level, subject } = chapter
  const marks = marksLabel(chapter)
  return (
    <Container className="max-w-3xl py-8 sm:py-10">
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
            <Link
              to="/courses/$course/$level/$subject"
              params={{ course, level, subject: subject.key }}
              className={CRUMB_LINK_CLASS}
            >
              <EntityCrumb kind="paper">{subject.name}</EntityCrumb>
            </Link>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>
              <EntityCrumb kind="chapter">{chapter.name}</EntityCrumb>
            </BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <EntityBadge kind="chapter" size="lg">
        Chapter
      </EntityBadge>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight break-words sm:text-3xl">{chapter.name}</h1>
      <p className="mt-2 flex flex-wrap items-center gap-2 text-muted-foreground">
        <EntityBadge kind="paper" size="lg">
          {subject.name}
        </EntityBadge>
        {chapter.section ? <Badge variant="outline">{chapter.section}</Badge> : null}
        {marks ? <Badge variant="outline">{marks}</Badge> : null}
        {chapter.est_study_minutes ? (
          <Badge variant="outline">About {Math.round(chapter.est_study_minutes / 60)} h to study</Badge>
        ) : null}
      </p>

      <section className="mt-6" aria-labelledby="topics-heading">
        <h2 id="topics-heading" className="flex items-center gap-2 text-base font-semibold">
          <EntityDot kind="topic" />
          {chapter.topics.length ? pluralize(chapter.topics.length, 'topic') : 'Topics'}
        </h2>
        {chapter.topics.length === 0 ? (
          <p className="mt-3 rounded-lg border border-dashed p-4 text-muted-foreground">
            The topic list is coming soon.
          </p>
        ) : (
          <ol className="mt-3 space-y-1.5">
            {chapter.topics.map((t) => (
              <li key={t.id}>
                <EntityListRow kind="topic" className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2.5">
                  <EntityTitle className="min-w-0 flex-1 basis-40 font-medium">{t.name}</EntityTitle>
                  {t.kind !== 'concept' ? <Badge variant="outline">{t.kind.replace('_', ' ')}</Badge> : null}
                </EntityListRow>
              </li>
            ))}
          </ol>
        )}
      </section>

      {chapter.prev_chapter || chapter.next_chapter ? (
        <nav aria-label="Chapters in this paper" className="mt-6 grid gap-2 sm:grid-cols-2">
          {chapter.prev_chapter ? (
            <Link
              to="/courses/$course/$level/$subject/$chapter"
              params={{ course, level, subject: subject.key, chapter: chapter.prev_chapter.key }}
              className="flex items-center gap-3 rounded-lg border p-3 hover:bg-muted/40"
            >
              <ArrowLeft aria-hidden className="size-5 shrink-0 text-muted-foreground" />
              <span className="min-w-0">
                <span className="block text-sm text-muted-foreground">Previous chapter</span>
                <span className="block font-medium">{chapter.prev_chapter.name}</span>
              </span>
            </Link>
          ) : (
            <span />
          )}
          {chapter.next_chapter ? (
            <Link
              to="/courses/$course/$level/$subject/$chapter"
              params={{ course, level, subject: subject.key, chapter: chapter.next_chapter.key }}
              className="flex items-center justify-end gap-3 rounded-lg border p-3 text-right hover:bg-muted/40"
            >
              <span className="min-w-0">
                <span className="block text-sm text-muted-foreground">Next chapter</span>
                <span className="block font-medium">{chapter.next_chapter.name}</span>
              </span>
              <ArrowRight aria-hidden className="size-5 shrink-0 text-muted-foreground" />
            </Link>
          ) : null}
        </nav>
      ) : null}

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Button variant="cta" arrow asChild>
          <Link to="/app/syllabus">Track this chapter</Link>
        </Button>
        {report}
      </div>
    </Container>
  )
}
