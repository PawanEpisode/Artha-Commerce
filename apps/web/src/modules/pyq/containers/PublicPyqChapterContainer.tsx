import { Badge, ButtonLink, Card, EmptyState, FileText, Play } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import * as React from 'react'

import type { ChapterPyqItem, SchemeRelation } from '../lib/types'

interface PublicPyqChapterContainerProps {
  courseName: string
  levelName: string
  subjectName: string
  chapterName: string
  courseSlug: string
  levelSlug: string
  subjectSlug: string
  chapterSlug: string
  items: ChapterPyqItem[]
}

const schemeRelationBadge: Record<SchemeRelation, { label: string; className: string }> = {
  current: {
    label: '2022 Syllabus',
    className: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
  },
  mapped: { label: 'Mapped', className: 'bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300' },
  changed: { label: 'Changed', className: 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300' },
  unmapped: { label: 'Out of Syllabus', className: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400' },
}

export function PublicPyqChapterContainer({
  courseName,
  levelName,
  subjectName,
  chapterName,
  courseSlug,
  levelSlug,
  subjectSlug,
  chapterSlug,
  items,
}: PublicPyqChapterContainerProps) {
  const [filterRelation, setFilterRelation] = React.useState<string>('all')

  const totalMarks = React.useMemo(() => {
    return items.reduce((sum, item) => sum + (parseFloat(item.marks) || 0), 0)
  }, [items])

  const termsCount = React.useMemo(() => {
    const terms = new Set(items.map((i) => i.term_code))
    return terms.size
  }, [items])

  const filteredItems = React.useMemo(() => {
    if (filterRelation === 'all') return items
    return items.filter((i) => i.scheme_relation === filterRelation)
  }, [items, filterRelation])

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-4 py-8">
      {/* Breadcrumb nav */}
      <nav aria-label="Breadcrumb" className="text-xs text-muted-foreground">
        <ol className="flex flex-wrap items-center gap-1.5">
          <li>
            <Link to="/courses" className="hover:text-foreground">
              Courses
            </Link>
          </li>
          <li>/</li>
          <li>
            <Link to="/courses/$course" params={{ course: courseSlug }} className="text-foreground hover:underline">
              {courseName}
            </Link>
          </li>
          <li>/</li>
          <li>
            <Link
              to="/courses/$course/$level"
              params={{ course: courseSlug, level: levelSlug }}
              className="text-foreground hover:underline"
            >
              {levelName}
            </Link>
          </li>
          <li>/</li>
          <li>
            <span className="text-foreground">{subjectName}</span>
          </li>
          <li>/</li>
          <li className="font-medium text-foreground">{chapterName}</li>
        </ol>
      </nav>

      {/* Header */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="font-semibold text-primary">
            Past Exam Questions (PYQ)
          </Badge>
          <Badge variant="default">
            {courseName} {levelName}
          </Badge>
        </div>

        <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">{chapterName}</h1>
        <p className="text-sm text-muted-foreground">
          Original exam questions and problems asked in past {courseName} exams for {subjectName}.
        </p>

        {/* Aggregate Stats */}
        <div className="grid grid-cols-2 gap-3 pt-2 sm:grid-cols-3">
          <Card className="p-3">
            <span className="block text-xs text-muted-foreground">Questions Asked</span>
            <span className="text-xl font-bold text-foreground">{items.length} questions</span>
          </Card>
          <Card className="p-3">
            <span className="block text-xs text-muted-foreground">Exam Sittings</span>
            <span className="text-xl font-bold text-foreground">{termsCount} terms</span>
          </Card>
          <Card className="p-3">
            <span className="block text-xs text-muted-foreground">Total Marks Weightage</span>
            <span className="text-xl font-bold text-foreground">{totalMarks} marks</span>
          </Card>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-border pb-3">
        <button
          type="button"
          onClick={() => setFilterRelation('all')}
          className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
            filterRelation === 'all'
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-muted-foreground hover:bg-muted/80'
          }`}
        >
          All Questions ({items.length})
        </button>
        <button
          type="button"
          onClick={() => setFilterRelation('current')}
          className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
            filterRelation === 'current'
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-muted-foreground hover:bg-muted/80'
          }`}
        >
          2022 Syllabus ({items.filter((i) => i.scheme_relation === 'current').length})
        </button>
      </div>

      {/* Questions list */}
      {filteredItems.length === 0 ? (
        <EmptyState
          icon={<FileText aria-hidden className="size-6" />}
          title="No previous year questions found"
          description="There are no past paper questions recorded for this filter."
        />
      ) : (
        <div className="space-y-3">
          {filteredItems.map((item) => {
            const rel = schemeRelationBadge[item.scheme_relation] || schemeRelationBadge.current
            const termLabel = item.term_code.replace('_', ' ').toUpperCase()

            return (
              <Card key={item.id} className="p-4 transition-colors hover:bg-muted/20">
                <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                  <div className="flex-1 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className="text-xs font-semibold text-primary">
                        {termLabel}
                      </Badge>
                      <span className="font-mono text-xs font-bold text-foreground">{item.number_label}</span>
                      <Badge variant="default" className="text-xs">
                        {item.marks} {item.marks === '1.0' || item.marks === '1' ? 'mark' : 'marks'}
                      </Badge>
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${rel.className}`}
                      >
                        {rel.label}
                      </span>
                    </div>

                    <p className="text-sm font-medium text-foreground">
                      {item.descriptor || `${item.paper_title} - ${item.number_label}`}
                    </p>

                    <div className="text-xs text-muted-foreground">
                      <span>Source: </span>
                      <Link
                        to="/app/pyq/papers/$id"
                        params={{ id: item.paper_id }}
                        className="text-primary hover:underline"
                      >
                        {item.paper_title}
                      </Link>
                      {item.answer_page_hint && <span> • Suggested Solution: {item.answer_page_hint}</span>}
                    </div>
                  </div>

                  <div className="shrink-0 self-end sm:self-center">
                    <ButtonLink asChild variant="outline" size="sm" className="gap-1.5">
                      <Link to="/app/questions/$id" params={{ id: item.question_id }}>
                        <Play className="size-3.5 fill-current" />
                        Practise
                      </Link>
                    </ButtonLink>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* CTA Banner */}
      <Card className="space-y-3 border-primary/20 bg-primary/5 p-6 text-center">
        <h3 className="text-base font-bold text-foreground">Master {chapterName} with Past Papers</h3>
        <p className="mx-auto max-w-lg text-xs text-muted-foreground">
          Practise all {items.length} questions in exam mode with instant scoring and suggested answers.
        </p>
        <div>
          <ButtonLink asChild className="gap-1.5">
            <Link to="/app/practice/new" search={{ subject: subjectSlug, chapter: chapterSlug }}>
              <Play className="size-4 fill-current" />
              Start Chapter Practice
            </Link>
          </ButtonLink>
        </div>
      </Card>
    </div>
  )
}
