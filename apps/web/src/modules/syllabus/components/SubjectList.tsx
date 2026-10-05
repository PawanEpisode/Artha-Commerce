import { Badge, ChevronRight, EntityBadge } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { pluralize } from '../lib/format'
import type { SyllabusGroup, SyllabusSubject } from '../lib/types'
import { EntityIndex, EntityListRow, EntityTitle, ROW_LINK_CLASS } from './EntityList'

interface Props {
  course: string
  level: string
  groups: SyllabusGroup[]
  subjects: SyllabusSubject[]
}

function SubjectCard({ course, level, subject }: { course: string; level: string; subject: SyllabusSubject }) {
  return (
    <li>
      <EntityListRow kind="paper">
        <Link
          to="/courses/$course/$level/$subject"
          params={{ course, level, subject: subject.key }}
          className={ROW_LINK_CLASS}
        >
          <EntityIndex kind="paper">{subject.paper_number ?? '·'}</EntityIndex>
          <span className="min-w-0 space-y-1.5">
            <EntityTitle>{subject.name}</EntityTitle>
            <span className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              {subject.chapter_count > 0 ? (
                <EntityBadge kind="chapter">{pluralize(subject.chapter_count, 'chapter')}</EntityBadge>
              ) : (
                <Badge variant="outline">Coming soon</Badge>
              )}
              {subject.total_marks ? <span>{subject.total_marks} marks</span> : null}
              {subject.is_optional ? <Badge variant="outline">Optional</Badge> : null}
            </span>
          </span>
          <ChevronRight aria-hidden className="size-5 shrink-0 text-muted-foreground" />
        </Link>
      </EntityListRow>
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
