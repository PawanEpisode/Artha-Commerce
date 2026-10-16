import {
  Badge,
  Bookmark,
  CircleAlert,
  CircleCheck,
  CircleX,
  DataTable,
  ShieldCheck,
  Skeleton,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { DIFFICULTY_LABELS, formatMarks, kindLabel } from '../lib/labels'
import type { QuestionCardData } from '../lib/types'

interface QuestionTableProps {
  questions: QuestionCardData[]
  /** Show the "Your result" column (personal overlay). */
  showOverlay?: boolean
  /** Link each stem to its detail page. Off on public pages, where the detail page needs a sign-in. */
  linked?: boolean
  className?: string
}

const STEM = 'line-clamp-2 min-w-0 flex-1 text-[13px] leading-5 font-medium text-foreground'

const sourceText = (q: QuestionCardData) => [q.source_name, q.source_year].filter(Boolean).join(' ')

/** Five small dots plus an accessible label: the level is never colour only. */
export function DifficultyDots({ level }: { level?: number }) {
  if (!level) return <span className="text-muted-foreground">-</span>
  const label = `Difficulty ${level} of 5${DIFFICULTY_LABELS[level] ? `, ${DIFFICULTY_LABELS[level]}` : ''}`
  return (
    <span role="img" aria-label={label} title={label} className="inline-flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <span
          key={i}
          aria-hidden
          className={`size-1.5 rounded-full ${i <= level ? 'bg-foreground/70' : 'bg-border'}`}
        />
      ))}
    </span>
  )
}

/** "Your result" as icon plus text (never colour only). Unknown or missing values read as not attempted. */
export function ResultLabel({ result }: { result?: string | null }): ReactNode {
  switch (result) {
    case 'correct':
      return (
        <span className="inline-flex items-center gap-1 text-success-fg">
          <CircleCheck aria-hidden className="size-3.5" /> Correct
        </span>
      )
    case 'incorrect':
      return (
        <span className="inline-flex items-center gap-1 text-destructive">
          <CircleX aria-hidden className="size-3.5" /> Incorrect
        </span>
      )
    case 'partial':
      return (
        <span className="inline-flex items-center gap-1 text-warning-fg">
          <CircleAlert aria-hidden className="size-3.5" /> Partial
        </span>
      )
    case 'skipped':
      return (
        <span className="inline-flex items-center gap-1 text-muted-foreground">
          <CircleAlert aria-hidden className="size-3.5" /> Skipped
        </span>
      )
    default:
      return <span className="text-muted-foreground">Not attempted</span>
  }
}

/** The question list as a dense table: stem first (a real link), then kind, marks, difficulty, source and your result. */
export function QuestionTable({ questions, showOverlay = true, linked = true, className }: QuestionTableProps) {
  return (
    <DataTable className={className}>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>Question</TableHead>
          <TableHead className="hidden sm:table-cell">Kind</TableHead>
          <TableHead className="hidden text-right sm:table-cell">Marks</TableHead>
          <TableHead className="hidden md:table-cell">Difficulty</TableHead>
          <TableHead className="hidden md:table-cell">Source</TableHead>
          {showOverlay ? <TableHead>Your result</TableHead> : null}
        </TableRow>
      </TableHeader>
      <TableBody>
        {questions.map((q) => (
          <TableRow key={q.id}>
            <TableCell className="min-w-48 py-2">
              <div className="flex items-start gap-2">
                {linked ? (
                  <Link
                    to="/app/questions/$id"
                    params={{ id: q.id }}
                    className={`${STEM} rounded-sm outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring/50`}
                  >
                    {q.stem_head}
                  </Link>
                ) : (
                  <p className={STEM}>{q.stem_head}</p>
                )}
                <span className="flex shrink-0 items-center gap-1.5 pt-0.5">
                  {q.is_verified ? (
                    <span role="img" aria-label="Verified" title="Verified" className="text-success-fg">
                      <ShieldCheck aria-hidden className="size-3.5" />
                    </span>
                  ) : null}
                  {q.is_bookmarked ? (
                    <span role="img" aria-label="Bookmarked" title="Bookmarked" className="text-warning">
                      <Bookmark aria-hidden className="size-3.5 fill-warning" />
                    </span>
                  ) : null}
                </span>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground sm:hidden">
                {kindLabel(q.kind)} · {formatMarks(q.marks)}
              </p>
            </TableCell>
            <TableCell className="hidden sm:table-cell">
              <Badge variant="outline">{kindLabel(q.kind)}</Badge>
            </TableCell>
            <TableCell className="hidden text-right tabular-nums sm:table-cell">{Number(q.marks)}</TableCell>
            <TableCell className="hidden md:table-cell">
              <DifficultyDots level={q.difficulty} />
            </TableCell>
            <TableCell className="hidden max-w-48 truncate text-muted-foreground md:table-cell">
              {sourceText(q) || '-'}
            </TableCell>
            {showOverlay ? (
              <TableCell className="text-xs whitespace-nowrap">
                <ResultLabel result={q.last_result} />
              </TableCell>
            ) : null}
          </TableRow>
        ))}
      </TableBody>
    </DataTable>
  )
}

/** Skeleton rows with the same column layout, shown while the first page loads. */
export function QuestionTableSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div role="status" aria-busy="true" aria-label="Loading questions">
      <DataTable>
        <TableBody>
          {Array.from({ length: rows }, (_, i) => (
            <TableRow key={i} className="hover:bg-transparent">
              <TableCell className="py-2">
                <Skeleton className="h-4 w-full max-w-md" />
              </TableCell>
              <TableCell className="hidden sm:table-cell">
                <Skeleton className="h-4 w-20" />
              </TableCell>
              <TableCell className="hidden md:table-cell">
                <Skeleton className="h-4 w-24" />
              </TableCell>
              <TableCell>
                <Skeleton className="h-4 w-16" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </DataTable>
    </div>
  )
}
