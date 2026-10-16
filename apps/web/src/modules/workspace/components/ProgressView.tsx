import { ProgressBar, ProgressRing } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { type ChapterCounts, progressSentence, type SubjectRow } from '~/modules/coverage'

interface Props {
  percent: number
  counts: ChapterCounts
  weakest: SubjectRow[]
}

/** Overall ring (average progress across chapters), the plain sentence, and the three papers furthest behind. */
export function ProgressView({ percent, counts, weakest }: Props) {
  return (
    <>
      <div className="flex items-center gap-3">
        <ProgressRing value={percent} label="Average progress across chapters" size={64}>
          <span className="text-sm font-semibold">{percent}%</span>
        </ProgressRing>
        <p className="min-w-0 text-[13px] text-muted-foreground">{progressSentence(counts)}</p>
      </div>
      {weakest.length > 0 ? (
        <ul className="space-y-2">
          {weakest.map((s) => (
            <li key={s.id} className="space-y-1">
              <p className="flex justify-between gap-2 text-[13px]">
                <span className="truncate">{s.name}</span>
                <span className="text-muted-foreground tabular-nums">{s.pct_simple}%</span>
              </p>
              <ProgressBar value={s.pct_simple} label={s.name} />
            </li>
          ))}
        </ul>
      ) : null}
      <Link
        to="/app/syllabus"
        className="mt-auto text-[13px] font-medium text-primary underline-offset-4 hover:underline"
      >
        Open the syllabus map
      </Link>
    </>
  )
}
