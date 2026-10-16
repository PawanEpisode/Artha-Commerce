import { Badge, DataTable, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@artha/design-system'

import { formatDuration } from '../lib/duration'
import type { TimeVsCoverage } from '../lib/types'

const FLAG_TEXT: Record<string, string> = {
  high_time_low_coverage: 'Lots of time, little covered',
  low_time_low_coverage: 'Little time and little covered',
}

/** Time spent against coverage for each chapter of one subject. A flag is a word, never only a colour. */
export function TimeVsCoverageTable({ data }: { data: TimeVsCoverage }) {
  return (
    <DataTable
      aria-label={`Time spent and coverage by chapter for ${data.subject.name}`}
      className="min-w-[32rem]"
      containerClassName="rounded-none border-0"
    >
      <TableHeader>
        <TableRow>
          <TableHead scope="col">Chapter</TableHead>
          <TableHead scope="col">Time</TableHead>
          <TableHead scope="col">Covered</TableHead>
          <TableHead scope="col">Note</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.chapters.map((c) => (
          <TableRow key={c.chapter_id}>
            <TableHead scope="row" className="h-9 text-[13px] font-medium tracking-normal text-foreground normal-case">
              {c.name}
            </TableHead>
            <TableCell className="tabular-nums">{formatDuration(c.seconds)}</TableCell>
            <TableCell className="tabular-nums">{Math.round(c.coverage_percent)}%</TableCell>
            <TableCell>{c.flag ? <Badge variant="highlight">{FLAG_TEXT[c.flag] ?? c.flag}</Badge> : null}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </DataTable>
  )
}
