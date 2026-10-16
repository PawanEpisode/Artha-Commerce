import {
  Badge,
  Button,
  ButtonLink,
  Card,
  Container,
  DataTable,
  EmptyState,
  FileText,
  Play,
  StatTile,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import * as React from 'react'

import { SchemeBadge } from '../components/SchemeBadge'
import { marksText, termLabel } from '../lib/labels'
import type { ChapterPyqItem } from '../lib/types'

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
    <Container className="space-y-6 py-8">
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
          <Badge variant="outline" className="text-primary">
            Past Exam Questions (PYQ)
          </Badge>
          <Badge variant="default">
            {courseName} {levelName}
          </Badge>
        </div>

        <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">{chapterName}</h1>
        <p className="text-sm text-muted-foreground">
          Original exam questions and problems asked in past {courseName} exams for {subjectName}.
        </p>

        <div className="grid grid-cols-1 gap-3 pt-1 sm:grid-cols-3">
          <StatTile label="Questions Asked" value={`${items.length} questions`} />
          <StatTile label="Exam Sittings" value={`${termsCount} terms`} />
          <StatTile label="Total Marks Weightage" value={`${totalMarks} marks`} />
        </div>
      </div>

      {/* Filters */}
      <div role="group" aria-label="Filter questions" className="flex flex-wrap items-center gap-1.5">
        <Button
          type="button"
          size="sm"
          variant={filterRelation === 'all' ? 'default' : 'outline'}
          aria-pressed={filterRelation === 'all'}
          onClick={() => setFilterRelation('all')}
        >
          All Questions ({items.length})
        </Button>
        <Button
          type="button"
          size="sm"
          variant={filterRelation === 'current' ? 'default' : 'outline'}
          aria-pressed={filterRelation === 'current'}
          onClick={() => setFilterRelation('current')}
        >
          2022 Syllabus ({items.filter((i) => i.scheme_relation === 'current').length})
        </Button>
      </div>

      {/* Questions list */}
      {filteredItems.length === 0 ? (
        <EmptyState
          icon={<FileText aria-hidden className="size-6" />}
          title="No previous year questions found"
          description="There are no past paper questions recorded for this filter."
        />
      ) : (
        <DataTable>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Term</TableHead>
              <TableHead>No.</TableHead>
              <TableHead>Question</TableHead>
              <TableHead className="hidden text-right sm:table-cell">Marks</TableHead>
              <TableHead className="hidden md:table-cell">Syllabus</TableHead>
              <TableHead className="hidden lg:table-cell">Source paper</TableHead>
              <TableHead className="text-right">
                <span className="sr-only">Action</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredItems.map((item) => (
              <TableRow key={item.id}>
                <TableCell className="whitespace-nowrap">
                  <Badge variant="outline">{termLabel(item.term_code)}</Badge>
                </TableCell>
                <TableCell className="font-mono text-xs font-semibold whitespace-nowrap">{item.number_label}</TableCell>
                <TableCell className="min-w-48 py-2">
                  <p className="line-clamp-2 font-medium text-foreground">
                    {item.descriptor || `${item.paper_title} - ${item.number_label}`}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground tabular-nums sm:hidden">
                    {marksText(item.marks)} {Number(item.marks) === 1 ? 'mark' : 'marks'}
                  </p>
                  {item.answer_page_hint && (
                    <p className="mt-0.5 text-xs text-muted-foreground">Suggested solution: {item.answer_page_hint}</p>
                  )}
                </TableCell>
                <TableCell className="hidden text-right tabular-nums sm:table-cell">{marksText(item.marks)}</TableCell>
                <TableCell className="hidden md:table-cell">
                  <SchemeBadge relation={item.scheme_relation} />
                </TableCell>
                <TableCell className="hidden max-w-56 truncate lg:table-cell">
                  <Link
                    to="/app/pyq/papers/$id"
                    params={{ id: item.paper_id }}
                    className="text-primary hover:underline"
                  >
                    {item.paper_title}
                  </Link>
                </TableCell>
                <TableCell className="text-right">
                  <ButtonLink asChild variant="outline" size="sm">
                    <Link
                      to="/app/questions/$id"
                      params={{ id: item.question_id }}
                      aria-label={`Practise ${item.number_label}`}
                    >
                      <Play aria-hidden className="size-3.5 fill-current" />
                      Practise
                    </Link>
                  </ButtonLink>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </DataTable>
      )}

      {/* CTA Banner */}
      <Card className="space-y-2 border-primary/20 bg-primary/5 p-4 text-center">
        <h2 className="text-base font-semibold text-foreground">Master {chapterName} with Past Papers</h2>
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
    </Container>
  )
}
