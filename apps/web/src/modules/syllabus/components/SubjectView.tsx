import {
  Badge,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
  Button,
  ChevronRight,
  Container,
  EntityBadge,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { type ReactNode, useState } from 'react'

import { groupBySection, marksLabel, matchesQuery, pluralize, SEARCH_THRESHOLD } from '../lib/format'
import type { SubjectSyllabus } from '../lib/types'
import { ChapterSearch } from './ChapterSearch'
import { EntityCrumb, EntityIndex, EntityListRow, EntityTitle, ROW_LINK_CLASS } from './EntityList'
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
  const [query, setQuery] = useState('')
  const shown = subject.chapters.filter((c) => matchesQuery(c.name, query))
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
            <BreadcrumbPage>
              <EntityCrumb kind="paper">{subject.name}</EntityCrumb>
            </BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <h1 className="text-4xl font-extrabold break-words sm:text-5xl">{subject.name}</h1>
      <p className="mt-3 flex flex-wrap items-center gap-2 text-lg text-muted-foreground">
        <EntityBadge kind="paper" size="lg">
          {subject.paper_number ? `Paper ${subject.paper_number}` : 'Paper'}
        </EntityBadge>
        {subject.total_marks ? <Badge variant="outline">{subject.total_marks} marks</Badge> : null}
        {subject.is_optional ? <Badge variant="outline">Optional</Badge> : null}
        {subject.chapters.length > 0 ? (
          <EntityBadge kind="chapter" size="lg">
            {pluralize(subject.chapters.length, 'chapter')}
          </EntityBadge>
        ) : null}
      </p>
      <div className="mt-3">
        <SyllabusMeta scheme={subject.scheme} body={body} />
        {subject.source_url ? (
          <a
            href={subject.source_url}
            rel="noopener noreferrer"
            target="_blank"
            className="mt-2 inline-block text-sm font-medium text-primary underline underline-offset-4"
          >
            Official paper syllabus ({body})
          </a>
        ) : null}
      </div>

      {subject.chapters.length === 0 ? (
        <p className="mt-10 rounded-xl border border-dashed p-6 text-muted-foreground">
          The chapter list for this paper is coming soon.
        </p>
      ) : (
        <div className="mt-10 space-y-8">
          {subject.chapters.length > SEARCH_THRESHOLD ? (
            <ChapterSearch value={query} onChange={setQuery} shown={shown.length} total={subject.chapters.length} />
          ) : null}
          {shown.length === 0 ? <p className="text-muted-foreground">No chapter matches that search.</p> : null}
          {groupBySection(shown).map((group) => {
            return (
              <section key={group.section || 'all'}>
                {group.section ? <h2 className="mb-3 font-display text-xl font-bold">{group.section}</h2> : null}
                <ol className="space-y-3">
                  {group.items.map((c) => (
                    <li key={c.id}>
                      <EntityListRow kind="chapter">
                        <Link
                          to="/courses/$course/$level/$subject/$chapter"
                          params={{ course, level, subject: subject.key, chapter: c.key }}
                          className={ROW_LINK_CLASS}
                        >
                          <EntityIndex kind="chapter">{subject.chapters.indexOf(c) + 1}</EntityIndex>
                          <span className="min-w-0 space-y-1.5">
                            <EntityTitle>{c.name}</EntityTitle>
                            <span className="flex flex-wrap items-center gap-2">
                              {c.topic_count ? (
                                <EntityBadge kind="topic">{pluralize(c.topic_count, 'topic')}</EntityBadge>
                              ) : null}
                              {marksLabel(c) ? <Badge variant="outline">{marksLabel(c)}</Badge> : null}
                            </span>
                          </span>
                          <ChevronRight aria-hidden className="size-5 shrink-0 text-muted-foreground" />
                        </Link>
                      </EntityListRow>
                    </li>
                  ))}
                </ol>
              </section>
            )
          })}
        </div>
      )}

      <div className="mt-10 flex flex-wrap items-center gap-3">
        <Button variant="cta" size="lg" arrow asChild>
          <Link to="/app/syllabus">Track {subject.name}</Link>
        </Button>
        {report}
      </div>
    </Container>
  )
}
