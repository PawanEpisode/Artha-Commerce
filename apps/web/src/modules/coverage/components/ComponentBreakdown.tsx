import { ProgressBar } from '@artha/design-system'

import { chapterActivities, formatProgress } from '../lib/rules'
import type { ChapterRow, CoverageSettings } from '../lib/types'

type Weights = Pick<CoverageSettings, 'w_read' | 'w_practice' | 'w_revise' | 'w_mock'>

/** The four parts behind a chapter's percent, with counts against targets. A part with target 0 is hidden (FR-17). */
export function ComponentBreakdown({ chapter, weights }: { chapter: ChapterRow; weights: Weights }) {
  const activities = chapterActivities(chapter)
  const rows = [
    {
      key: 'read',
      label: 'Reading',
      pct: chapter.components.read,
      detail: `${chapter.topics_done} of ${chapter.topics_total} topics`,
      weight: weights.w_read,
      show: true,
    },
    {
      key: 'practice',
      label: 'Practice',
      pct: chapter.components.practice,
      detail: formatProgress(activities.practice, 'sets'),
      weight: weights.w_practice,
      show: chapter.targets.practice > 0,
    },
    {
      key: 'revise',
      label: 'Revision',
      pct: chapter.components.revise,
      detail: formatProgress(activities.revisions, 'rounds'),
      weight: weights.w_revise,
      show: chapter.targets.revisions > 0,
    },
    {
      key: 'mock',
      label: 'Mock tests',
      pct: chapter.components.mock,
      detail: formatProgress(activities.mocks, 'tests'),
      weight: weights.w_mock,
      show: chapter.targets.mocks > 0,
    },
  ].filter((r) => r.show)

  return (
    <dl className="space-y-4">
      {rows.map((r) => (
        <div key={r.key} className="space-y-1.5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <dt className="font-medium">
              {r.label} <span className="text-sm font-normal text-muted-foreground">({r.weight}% of the total)</span>
            </dt>
            <dd className="text-sm text-muted-foreground tabular-nums">
              {r.detail}, <span className="font-semibold text-foreground">{r.pct}%</span>
            </dd>
          </div>
          <ProgressBar value={r.pct} label={`${r.label} component`} />
        </div>
      ))}
    </dl>
  )
}
