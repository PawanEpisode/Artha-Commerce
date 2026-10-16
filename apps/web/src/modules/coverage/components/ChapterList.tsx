import {
  Badge,
  ConfidenceDot,
  DataTable,
  Label,
  Switch,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableToolbar,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { Fragment, useState } from 'react'

import { ChapterSearch, groupBySection, matchesQuery, SEARCH_THRESHOLD } from '~/modules/syllabus'

import type { ChapterRow } from '../lib/types'
import { ProgressCell } from './ProgressCell'
import { StatusBadge } from './StatusBadge'

/** Chapters of one paper as a dense table: number, name, status, confidence (beside the measured percent, FR-21) and progress. */
export function ChapterList({ subjectId, chapters }: { subjectId: string; chapters: ChapterRow[] }) {
  const [query, setQuery] = useState('')
  const [notStartedOnly, setNotStartedOnly] = useState(false)
  const shown = chapters.filter(
    (c) => matchesQuery(c.name, query) && (!notStartedOnly || (c.status === 'not_started' && !c.is_excluded)),
  )
  const filterable = chapters.length > SEARCH_THRESHOLD
  return (
    <div className="space-y-3">
      {filterable ? (
        <TableToolbar className="items-end gap-x-4">
          <div className="min-w-0 flex-1 basis-56 sm:max-w-sm">
            <ChapterSearch value={query} onChange={setQuery} shown={shown.length} total={chapters.length} />
          </div>
          <div className="flex items-center gap-2 pb-1.5">
            <Switch id="not-started-only" checked={notStartedOnly} onCheckedChange={setNotStartedOnly} />
            <Label htmlFor="not-started-only">Show only chapters I have not started</Label>
          </div>
        </TableToolbar>
      ) : null}
      {shown.length === 0 ? <p className="text-[13px] text-muted-foreground">No chapter matches.</p> : null}
      {shown.length > 0 ? (
        <DataTable aria-label="Chapters">
          <TableHeader>
            <TableRow>
              <TableHead className="w-10 text-center">No.</TableHead>
              <TableHead>Chapter</TableHead>
              <TableHead className="hidden sm:table-cell">Status</TableHead>
              <TableHead className="hidden md:table-cell">Confidence</TableHead>
              <TableHead className="text-right">Progress</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {groupBySection(shown).map((group) => (
              <Fragment key={group.section || 'all'}>
                {group.section ? (
                  <TableRow className="bg-muted/40 hover:bg-muted/40">
                    <TableCell colSpan={5} className="h-8 text-xs font-semibold">
                      {group.section}
                    </TableCell>
                  </TableRow>
                ) : null}
                {group.items.map((c) => (
                  <ChapterItem key={c.id} subjectId={subjectId} chapter={c} index={chapters.indexOf(c)} />
                ))}
              </Fragment>
            ))}
          </TableBody>
        </DataTable>
      ) : null}
    </div>
  )
}

function ChapterItem({ subjectId, chapter: c, index }: { subjectId: string; chapter: ChapterRow; index: number }) {
  return (
    <TableRow className={c.is_excluded ? 'opacity-70' : undefined}>
      <TableCell className="w-10 text-center text-xs text-muted-foreground tabular-nums">{index + 1}</TableCell>
      <TableCell className="min-w-44 whitespace-normal">
        <Link
          to="/app/syllabus/$subject/$chapter"
          params={{ subject: subjectId, chapter: c.id }}
          title={c.name}
          className="line-clamp-2 font-medium break-words underline-offset-4 outline-none hover:underline focus-visible:underline focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          {c.name}
        </Link>
      </TableCell>
      <TableCell className="hidden sm:table-cell">
        {c.is_excluded ? <Badge variant="outline">Excluded</Badge> : <StatusBadge status={c.status} />}
      </TableCell>
      <TableCell className="hidden md:table-cell">
        {c.confidence ? <ConfidenceDot value={c.confidence} showLabel /> : null}
      </TableCell>
      <TableCell className="text-right">
        {c.is_excluded ? null : <ProgressCell value={c.coverage_pct} label={`${c.name} coverage`} />}
      </TableCell>
    </TableRow>
  )
}
