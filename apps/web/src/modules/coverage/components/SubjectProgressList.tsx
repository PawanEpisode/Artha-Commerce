import { Badge, DataTable, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { Fragment } from 'react'

import { pick } from '../lib/formula'
import type { ElectiveSlot, GroupRow, SubjectRow } from '../lib/types'
import { ProgressCell } from './ProgressCell'

interface Props {
  groups: GroupRow[]
  subjects: SubjectRow[]
  electives?: ElectiveSlot[]
  weighted: boolean
  /** An explicit ?view on the map, carried to the paper screen so both show the same numbers. */
  view?: 'weighted' | 'simple'
}

function Row({
  subject,
  weighted,
  notChosen,
  view,
}: {
  subject: SubjectRow
  weighted: boolean
  notChosen: boolean
  view?: 'weighted' | 'simple'
}) {
  const pct = pick(subject, weighted)
  const allExcluded = subject.chapters_total === 0
  return (
    <TableRow>
      <TableCell className="w-10 text-center text-xs text-muted-foreground tabular-nums">
        {subject.paper_number ?? '·'}
      </TableCell>
      <TableCell className="min-w-44 whitespace-normal">
        <Link
          to="/app/syllabus/$subject"
          params={{ subject: subject.id }}
          search={view ? { view } : {}}
          title={subject.name}
          className="line-clamp-2 font-medium break-words underline-offset-4 outline-none hover:underline focus-visible:underline focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          {subject.name}
        </Link>
      </TableCell>
      <TableCell className="hidden sm:table-cell">
        <div className="flex flex-wrap items-center gap-1">
          {subject.elective_slot ? (
            <Badge variant="outline">{notChosen ? 'Elective: not chosen' : 'Your elective'}</Badge>
          ) : null}
          {subject.excluded_chapters > 0 && !subject.elective_slot ? (
            <Badge variant="outline">{subject.excluded_chapters} excluded</Badge>
          ) : null}
        </div>
      </TableCell>
      <TableCell className="text-right">
        <ProgressCell value={pct} label={`${subject.name} coverage`} na={allExcluded} />
      </TableCell>
    </TableRow>
  )
}

/** Groups (Group 1, Group 2) with their papers as one dense table: the paper, its flags, a thin bar and the percent. */
export function SubjectProgressList({ groups, subjects: allSubjects, electives = [], weighted, view }: Props) {
  // Once an elective is chosen the other options are out of the student's syllabus; until then all of them are listed.
  const chosenBySlot = new Map(electives.map((e) => [e.key, e.chosen]))
  const subjects = allSubjects.filter((s) => {
    const chosen = s.elective_slot ? chosenBySlot.get(s.elective_slot) : null
    return !chosen || chosen === s.id
  })
  const sections = groups.length
    ? [
        ...groups.map((g) => ({
          id: g.id,
          name: g.name,
          pct: pick(g, weighted),
          items: subjects.filter((s) => s.group_key === g.key),
        })),
        {
          id: 'other',
          name: 'Other papers',
          pct: null,
          items: subjects.filter((s) => !groups.some((g) => g.key === s.group_key)),
        },
      ].filter((s) => s.items.length)
    : [{ id: 'all', name: '', pct: null, items: subjects }]

  return (
    <DataTable aria-label="Papers">
      <TableHeader>
        <TableRow>
          <TableHead className="w-10 text-center">No.</TableHead>
          <TableHead>Paper</TableHead>
          <TableHead className="hidden sm:table-cell">
            <span className="sr-only">Flags</span>
          </TableHead>
          <TableHead className="text-right">Progress</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sections.map((section) => (
          <Fragment key={section.id}>
            {section.name ? (
              <TableRow className="bg-muted/40 hover:bg-muted/40">
                <TableCell colSpan={3} className="h-8 text-xs font-semibold">
                  {section.name}
                </TableCell>
                <TableCell className="h-8 text-right text-xs font-semibold text-muted-foreground tabular-nums">
                  {section.pct !== null ? `${section.pct}%` : ''}
                </TableCell>
              </TableRow>
            ) : null}
            {section.items.map((s) => (
              <Row
                key={s.id}
                subject={s}
                weighted={weighted}
                view={view}
                notChosen={Boolean(s.elective_slot) && !chosenBySlot.get(s.elective_slot ?? '')}
              />
            ))}
          </Fragment>
        ))}
      </TableBody>
    </DataTable>
  )
}
