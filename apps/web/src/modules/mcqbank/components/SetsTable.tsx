import {
  Badge,
  Button,
  ButtonLink,
  DataTable,
  Play,
  ShieldCheck,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { McqSetCard } from '../lib/types'

interface SetsTableProps {
  sets: McqSetCard[]
  /** Start a hosted set. Omit on public pages: the title still links to the set. */
  onStartPractice?: (slug: string) => void
  onOpenExternalLog?: (set: McqSetCard) => void
  isStarting?: boolean
  className?: string
}

const kindText = (kind: string) => kind.replace(/_/g, ' ')

/** MCQ practice sets as a table: set (link), kind, source, questions, time and the action that fits its delivery. */
export function SetsTable({ sets, onStartPractice, onOpenExternalLog, isStarting, className }: SetsTableProps) {
  return (
    <DataTable className={className}>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>Set</TableHead>
          <TableHead className="hidden sm:table-cell">Kind</TableHead>
          <TableHead className="hidden md:table-cell">Source</TableHead>
          <TableHead className="text-right">MCQs</TableHead>
          <TableHead className="hidden text-right sm:table-cell">Time</TableHead>
          <TableHead className="text-right">
            <span className="sr-only">Action</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sets.map((set) => {
          const isHosted = set.delivery === 'hosted'
          const isLinkOut = set.delivery === 'link_out'
          return (
            <TableRow key={set.id}>
              <TableCell className="min-w-48 py-2">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                  <Link
                    to="/app/mcq/sets/$slug"
                    params={{ slug: set.slug }}
                    className="rounded-sm font-medium text-foreground outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring/50"
                  >
                    {set.title}
                  </Link>
                  {set.featured && <Badge>Featured</Badge>}
                  {set.verified && (
                    <span className="inline-flex items-center gap-1 text-xs text-success-fg">
                      <ShieldCheck aria-hidden className="size-3.5" /> Verified
                    </span>
                  )}
                </div>
                {set.description && (
                  <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">{set.description}</p>
                )}
              </TableCell>
              <TableCell className="hidden sm:table-cell">
                <Badge variant="outline" className="uppercase">
                  {kindText(set.set_kind)}
                </Badge>
              </TableCell>
              <TableCell className="hidden max-w-48 truncate text-muted-foreground md:table-cell">
                {set.source_name || '-'}
              </TableCell>
              <TableCell className="text-right tabular-nums">{set.question_count}</TableCell>
              <TableCell className="hidden text-right text-muted-foreground tabular-nums sm:table-cell">
                {set.est_minutes > 0 ? `${set.est_minutes}m` : '-'}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex flex-wrap items-center justify-end gap-1.5">
                  {isHosted && onStartPractice ? (
                    <Button size="sm" disabled={isStarting} onClick={() => onStartPractice(set.slug)}>
                      <Play aria-hidden className="size-3.5 fill-current" />
                      Practice Online
                    </Button>
                  ) : null}
                  {isLinkOut && set.source_url ? (
                    <ButtonLink size="sm" variant="outline" href={set.source_url} target="_blank" rel="noreferrer">
                      Open ICMAI PDF
                    </ButtonLink>
                  ) : null}
                  {isLinkOut && onOpenExternalLog ? (
                    <Button size="sm" onClick={() => onOpenExternalLog(set)}>
                      Log Offline Score
                    </Button>
                  ) : null}
                </div>
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </DataTable>
  )
}
