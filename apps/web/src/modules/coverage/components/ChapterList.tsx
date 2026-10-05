import { Badge, ChevronRight, ConfidenceDot, Label, ProgressBar, Switch } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'

import {
  ChapterSearch,
  EntityIndex,
  EntityListRow,
  EntityTitle,
  groupBySection,
  matchesQuery,
  ROW_LINK_CLASS,
  SEARCH_THRESHOLD,
} from '~/modules/syllabus'

import type { ChapterRow } from '../lib/types'
import { StatusBadge } from './StatusBadge'

/** Chapters of one subject: percent, status, confidence (beside the measured percent, FR-21). */
export function ChapterList({ subjectId, chapters }: { subjectId: string; chapters: ChapterRow[] }) {
  const [query, setQuery] = useState('')
  const [notStartedOnly, setNotStartedOnly] = useState(false)
  const shown = chapters.filter(
    (c) => matchesQuery(c.name, query) && (!notStartedOnly || (c.status === 'not_started' && !c.is_excluded)),
  )
  const filterable = chapters.length > SEARCH_THRESHOLD
  return (
    <div className="space-y-8">
      {filterable ? (
        <div className="space-y-3">
          <ChapterSearch value={query} onChange={setQuery} shown={shown.length} total={chapters.length} />
          <div className="flex items-center gap-3">
            <Switch id="not-started-only" checked={notStartedOnly} onCheckedChange={setNotStartedOnly} />
            <Label htmlFor="not-started-only">Show only chapters I have not started</Label>
          </div>
        </div>
      ) : null}
      {shown.length === 0 ? <p className="text-muted-foreground">No chapter matches.</p> : null}
      {groupBySection(shown).map((group) => (
        <section key={group.section || 'all'}>
          {group.section ? <h2 className="mb-3 font-display text-xl font-bold">{group.section}</h2> : null}
          <ol className="space-y-3">
            {group.items.map((c) => (
              <ChapterItem key={c.id} subjectId={subjectId} chapter={c} index={chapters.indexOf(c)} />
            ))}
          </ol>
        </section>
      ))}
    </div>
  )
}

function ChapterItem({ subjectId, chapter: c, index }: { subjectId: string; chapter: ChapterRow; index: number }) {
  return (
    <li>
      <EntityListRow kind="chapter" className={c.is_excluded ? 'opacity-70' : undefined}>
        <Link
          to="/app/syllabus/$subject/$chapter"
          params={{ subject: subjectId, chapter: c.id }}
          className={ROW_LINK_CLASS}
        >
          <EntityIndex kind="chapter">{index + 1}</EntityIndex>
          <span className="min-w-0 space-y-2">
            <EntityTitle>{c.name}</EntityTitle>
            <span className="flex flex-wrap items-center gap-2">
              {c.is_excluded ? <Badge variant="outline">Excluded</Badge> : <StatusBadge status={c.status} />}
              {c.confidence ? <ConfidenceDot value={c.confidence} showLabel /> : null}
            </span>
            {c.is_excluded ? null : <ProgressBar size="sm" value={c.coverage_pct} label={`${c.name} coverage`} />}
          </span>
          <span className="flex items-center gap-1">
            <span className="w-12 text-right font-display text-lg font-bold tabular-nums">
              {c.is_excluded ? '' : `${c.coverage_pct}%`}
            </span>
            <ChevronRight aria-hidden className="size-5 shrink-0 text-muted-foreground" />
          </span>
        </Link>
      </EntityListRow>
    </li>
  )
}
