import { DataTable, ProgressBar, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@artha/design-system'

import { formatDuration } from '../lib/duration'
import type { Breakdown } from '../lib/types'

/** Share of time per subject or activity: the name, a bar, the time and the percentage in words. */
export function BreakdownList({ title, data }: { title: string; data: Breakdown }) {
  return (
    <section aria-label={title} className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      {data.items.length === 0 ? (
        <p className="text-[13px] text-muted-foreground">No study time in this range.</p>
      ) : (
        <DataTable aria-label={`${title}, share of study time`}>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead className="max-sm:hidden">Share</TableHead>
              <TableHead className="text-right">Time</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((item) => (
              <TableRow key={item.key}>
                <TableCell className="max-w-0 min-w-24 truncate font-medium">{item.name}</TableCell>
                <TableCell className="w-32 max-sm:hidden">
                  <ProgressBar value={item.share_percent} label={`${item.name} share of time`} size="sm" />
                </TableCell>
                <TableCell className="text-right whitespace-nowrap text-muted-foreground tabular-nums">
                  {formatDuration(item.seconds)} · {Math.round(item.share_percent)}%
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </DataTable>
      )}
    </section>
  )
}
