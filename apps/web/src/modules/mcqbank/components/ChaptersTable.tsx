import {
  Badge,
  Button,
  DataTable,
  Play,
  ProgressBar,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { ChapterTile } from '../lib/types'

interface ChaptersTableProps {
  chapters: ChapterTile[]
  subjectKey: string
  onQuickPractice?: (chapterId: string) => void
  isStarting?: boolean
}

/** Chapters of a subject as a table (each name opens the chapter's questions): coverage, recent accuracy, what is unseen, wrong or due, and a quick 10-MCQ start. */
export function ChaptersTable({ chapters, subjectKey, onQuickPractice, isStarting }: ChaptersTableProps) {
  return (
    <DataTable>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>Chapter</TableHead>
          <TableHead className="hidden lg:table-cell">Section</TableHead>
          <TableHead className="text-right">MCQs</TableHead>
          <TableHead className="hidden w-40 sm:table-cell">Coverage</TableHead>
          <TableHead className="hidden text-right md:table-cell">Accuracy</TableHead>
          <TableHead className="hidden lg:table-cell">To do</TableHead>
          <TableHead className="text-right">
            <span className="sr-only">Action</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {chapters.map((ch) => {
          const attempted = ch.available - ch.unseen
          const progressPct = ch.available > 0 ? Math.round((attempted / ch.available) * 100) : 0
          return (
            <TableRow key={ch.chapter_id}>
              <TableCell className="min-w-40 py-2">
                <Link
                  to="/app/mcq/subjects/$subject/chapters/$chapter"
                  params={{ subject: subjectKey, chapter: ch.chapter_key }}
                  className="line-clamp-2 rounded-sm font-medium text-foreground outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring/50"
                >
                  {ch.name}
                </Link>
                <p className="mt-0.5 text-xs text-muted-foreground tabular-nums sm:hidden">
                  {progressPct}% covered
                  {ch.accuracy_recent !== null ? ` · ${ch.accuracy_recent}% acc.` : ''}
                </p>
              </TableCell>
              <TableCell className="hidden text-muted-foreground lg:table-cell">{ch.section || '-'}</TableCell>
              <TableCell className="text-right tabular-nums">{ch.available}</TableCell>
              <TableCell className="hidden sm:table-cell">
                <div className="flex items-center gap-2">
                  <ProgressBar value={progressPct} label={`${ch.name} coverage`} className="h-1.5 flex-1" />
                  <span className="w-9 text-right text-xs text-muted-foreground tabular-nums">{progressPct}%</span>
                </div>
              </TableCell>
              <TableCell className="hidden text-right tabular-nums md:table-cell">
                {ch.accuracy_recent !== null ? (
                  `${ch.accuracy_recent}%`
                ) : (
                  <span className="text-muted-foreground">Not attempted</span>
                )}
              </TableCell>
              <TableCell className="hidden lg:table-cell">
                <span className="flex flex-wrap gap-1">
                  {ch.unseen > 0 && <Badge variant="outline">{ch.unseen} unseen</Badge>}
                  {ch.wrong_last > 0 && (
                    <Badge variant="outline" className="border-destructive/30 text-destructive">
                      {ch.wrong_last} mistakes
                    </Badge>
                  )}
                  {ch.due > 0 && <Badge variant="default">{ch.due} due for review</Badge>}
                  {ch.unseen === 0 && ch.wrong_last === 0 && ch.due === 0 && (
                    <span className="text-muted-foreground">-</span>
                  )}
                </span>
              </TableCell>
              <TableCell className="text-right">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={isStarting || ch.available === 0}
                  onClick={() => onQuickPractice?.(ch.chapter_id)}
                  aria-label={`Quick 10 MCQs: ${ch.name}`}
                >
                  <Play aria-hidden className="size-3.5 fill-current" />
                  Quick 10
                </Button>
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </DataTable>
  )
}
