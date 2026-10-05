import { Badge, Card, ChevronRight, ProgressBar } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { pick } from '../lib/formula'
import type { ElectiveSlot, GroupRow, SubjectRow } from '../lib/types'

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
    <li>
      <Card className="focus-within:ring-[3px] focus-within:ring-ring/40 hover:shadow-(--shadow-soft)">
        <Link
          to="/app/syllabus/$subject"
          params={{ subject: subject.id }}
          search={view ? { view } : {}}
          className="flex items-center gap-4 rounded-xl p-4 outline-none"
        >
          <span className="min-w-0 flex-1 space-y-2">
            <span className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">{subject.name}</span>
              {subject.elective_slot ? (
                <Badge variant="outline">{notChosen ? 'Elective: not chosen' : 'Your elective'}</Badge>
              ) : null}
              {subject.excluded_chapters > 0 && !subject.elective_slot ? (
                <Badge variant="outline">{subject.excluded_chapters} excluded</Badge>
              ) : null}
            </span>
            <ProgressBar value={pct} label={`${subject.name} coverage`} />
          </span>
          <span className="w-12 shrink-0 text-right font-display text-lg font-bold tabular-nums">
            {allExcluded ? 'n/a' : `${pct}%`}
          </span>
          <ChevronRight aria-hidden className="size-5 shrink-0 text-muted-foreground" />
        </Link>
      </Card>
    </li>
  )
}

/** Groups (Group 1, Group 2) with their papers, each with a bar and percent. */
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
    <div className="space-y-8">
      {sections.map((section) => (
        <section key={section.id} aria-label={section.name || 'Papers'}>
          {section.name ? (
            <h2 className="mb-3 flex items-baseline justify-between font-display text-lg font-bold">
              {section.name}
              {section.pct !== null ? (
                <span className="text-sm font-semibold text-muted-foreground tabular-nums">{section.pct}%</span>
              ) : null}
            </h2>
          ) : null}
          <ul className="space-y-3">
            {section.items.map((s) => (
              <Row
                key={s.id}
                subject={s}
                weighted={weighted}
                view={view}
                notChosen={Boolean(s.elective_slot) && !chosenBySlot.get(s.elective_slot ?? '')}
              />
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
