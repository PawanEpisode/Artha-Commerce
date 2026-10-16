import {
  Badge,
  Button,
  DataTable,
  Play,
  Skeleton,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { levelLabel, marksText, termLabel } from '../lib/labels'
import type { PyqPaperCard } from '../lib/types'

interface PapersTableProps {
  papers: PyqPaperCard[]
  onStartPractice?: (paperId: string) => void
  startingPaperId?: string | null
}

/** Past papers as a table: paper (link), term, code, syllabus, marks, questions, your progress, and the actions. */
export function PapersTable({ papers, onStartPractice, startingPaperId }: PapersTableProps) {
  return (
    <DataTable>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>Paper</TableHead>
          <TableHead className="hidden sm:table-cell">Term</TableHead>
          <TableHead className="hidden lg:table-cell">Syllabus</TableHead>
          <TableHead className="hidden text-right sm:table-cell">Marks</TableHead>
          <TableHead className="hidden text-right md:table-cell">Questions</TableHead>
          <TableHead className="hidden md:table-cell">Progress</TableHead>
          <TableHead className="text-right">
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {papers.map((paper) => {
          const isInteractive = paper.delivery === 'digitised_interactive'
          const isStarting = startingPaperId === paper.id
          return (
            <TableRow key={paper.id}>
              <TableCell className="min-w-48 py-2">
                <Link
                  to="/app/pyq/papers/$id"
                  params={{ id: paper.id }}
                  className="line-clamp-2 rounded-sm font-medium text-foreground outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring/50"
                >
                  {paper.title}
                </Link>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {paper.course_code.toUpperCase()} {levelLabel(paper.level_code)}
                  <span className="sm:hidden"> · {termLabel(paper.term_code)}</span>
                </p>
              </TableCell>
              <TableCell className="hidden sm:table-cell">
                <span className="flex flex-wrap items-center gap-1">
                  <Badge variant="outline">{termLabel(paper.term_code)}</Badge>
                  <Badge className="uppercase">{paper.paper_code || paper.subject_key}</Badge>
                </span>
              </TableCell>
              <TableCell className="hidden lg:table-cell">
                {paper.syllabus_status === 'current' ? (
                  <Badge variant="outline" className="border-success-border bg-success-bg text-success-fg">
                    2022 Syllabus
                  </Badge>
                ) : (
                  <Badge variant="outline" className="border-warning-border bg-warning-bg text-warning-fg">
                    Mapped Syllabus
                  </Badge>
                )}
              </TableCell>
              <TableCell className="hidden text-right tabular-nums sm:table-cell">
                {marksText(paper.total_marks)}
              </TableCell>
              <TableCell className="hidden text-right text-muted-foreground tabular-nums md:table-cell">
                {paper.question_count}
              </TableCell>
              <TableCell className="hidden whitespace-nowrap text-muted-foreground tabular-nums md:table-cell">
                {paper.attempted_count} / {paper.question_count} attempted
              </TableCell>
              <TableCell className="text-right whitespace-nowrap">
                {onStartPractice && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onStartPractice(paper.id)}
                    disabled={isStarting}
                    aria-label={`${isInteractive ? 'Simulate exam' : 'Practise paper'}: ${paper.title}`}
                  >
                    <Play aria-hidden className="size-3.5 fill-current" />
                    {isStarting ? 'Starting...' : isInteractive ? 'Simulate' : 'Practise'}
                  </Button>
                )}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </DataTable>
  )
}

export function PapersTableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div role="status" aria-busy="true" aria-label="Loading past papers">
      <DataTable>
        <TableBody>
          {Array.from({ length: rows }, (_, i) => (
            <TableRow key={i} className="hover:bg-transparent">
              <TableCell className="py-2">
                <Skeleton className="h-4 w-56 max-w-full" />
              </TableCell>
              <TableCell className="hidden sm:table-cell">
                <Skeleton className="h-4 w-28" />
              </TableCell>
              <TableCell className="hidden md:table-cell">
                <Skeleton className="h-4 w-20" />
              </TableCell>
              <TableCell>
                <Skeleton className="h-6 w-20" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </DataTable>
    </div>
  )
}
