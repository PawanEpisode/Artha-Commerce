import { Badge, Card, ChevronRight, ProgressBar } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { pick } from '../lib/formula'
import type { GroupRow, SubjectRow } from '../lib/types'

interface Props {
  groups: GroupRow[]
  subjects: SubjectRow[]
  weighted: boolean
}

function Row({ subject, weighted }: { subject: SubjectRow; weighted: boolean }) {
  const pct = pick(subject, weighted)
  const allExcluded = subject.chapters_total === 0
  return (
    <li>
      <Card className="focus-within:ring-[3px] focus-within:ring-ring/40 hover:shadow-(--shadow-soft)">
        <Link
          to="/app/syllabus/$subject"
          params={{ subject: subject.id }}
          className="flex items-center gap-4 rounded-xl p-4 outline-none"
        >
          <span className="min-w-0 flex-1 space-y-2">
            <span className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">{subject.name}</span>
              {subject.excluded_chapters > 0 ? (
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
export function SubjectProgressList({ groups, subjects, weighted }: Props) {
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
              <Row key={s.id} subject={s} weighted={weighted} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
