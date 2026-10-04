import { Badge, Card, ChevronRight } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { pluralize } from '../lib/format'
import type { SyllabusGroup, SyllabusSubject } from '../lib/types'

interface Props {
  course: string
  level: string
  groups: SyllabusGroup[]
  subjects: SyllabusSubject[]
}

function SubjectCard({ course, level, subject }: { course: string; level: string; subject: SyllabusSubject }) {
  return (
    <li>
      <Card className="transition-shadow focus-within:ring-[3px] focus-within:ring-ring/40 hover:shadow-(--shadow-soft)">
        <Link
          to="/courses/$course/$level/$subject"
          params={{ course, level, subject: subject.key }}
          className="flex items-center gap-4 rounded-xl p-4 outline-none"
        >
          <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-secondary font-display font-bold text-primary">
            {subject.paper_number ?? '·'}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block font-semibold">{subject.name}</span>
            <span className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              {subject.chapter_count > 0 ? (
                <span>{pluralize(subject.chapter_count, 'chapter')}</span>
              ) : (
                <Badge variant="outline">Coming soon</Badge>
              )}
              {subject.total_marks ? <span>{subject.total_marks} marks</span> : null}
              {subject.is_optional ? <Badge variant="outline">Optional</Badge> : null}
            </span>
          </span>
          <ChevronRight aria-hidden className="size-5 shrink-0 text-muted-foreground" />
        </Link>
      </Card>
    </li>
  )
}

/** Papers of a level, grouped (Group 1, Group 2) when the scheme has groups. */
export function SubjectList({ course, level, groups, subjects }: Props) {
  const sections = groups.length
    ? [
        ...groups.map((g) => ({ id: g.id, name: g.name, items: subjects.filter((s) => s.group_key === g.key) })),
        {
          id: 'ungrouped',
          name: 'Other papers',
          items: subjects.filter((s) => !groups.some((g) => g.key === s.group_key)),
        },
      ].filter((s) => s.items.length > 0)
    : [{ id: 'all', name: '', items: subjects }]

  return (
    <div className="space-y-8">
      {sections.map((section) => (
        <section key={section.id} aria-label={section.name || 'Papers'}>
          {section.name ? <h2 className="mb-3 font-display text-xl font-bold">{section.name}</h2> : null}
          <ul className="space-y-3">
            {section.items.map((s) => (
              <SubjectCard key={s.id} course={course} level={level} subject={s} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
