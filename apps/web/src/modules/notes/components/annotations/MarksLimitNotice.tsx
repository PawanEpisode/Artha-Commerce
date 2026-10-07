import { Alert } from '@artha/design-system'

import { type HeavyPage, inkSizeLabel, type MarksNotice } from '../../lib/annotation-limits'
import type { MarksInfo } from '../../lib/annotation-types'

export interface MarksLimitNoticeProps {
  notice: MarksNotice
  info: Pick<MarksInfo, 'count' | 'limit'>
  /** Pages with the most ink, heaviest first (shown at the cap, where the student has to free room). */
  heavyPages: readonly HeavyPage[]
  onGoToPage?: (page: number) => void
}

const fmt = (n: number) => n.toLocaleString('en-IN')

/**
 * The quiet notice at 95% of a PDF's marks and the blocked state at 100% (PRD 7.3). It says how many marks are used and
 * what to delete first: pages with a lot of ink weigh the most.
 */
export function MarksLimitNotice({ notice, info, heavyPages, onGoToPage }: MarksLimitNoticeProps) {
  if (notice === 'ok') return null
  const blocked = notice === 'blocked'
  return (
    <Alert variant={blocked ? 'error' : 'info'} data-slot="marks-limit">
      <p className="font-semibold">
        {blocked ? 'This PDF has reached its limit of marks.' : 'This PDF is nearly full of marks.'}
      </p>
      <p className="mt-1 text-muted-foreground">
        {fmt(info.count)} of {fmt(info.limit)} used.{' '}
        {blocked ? 'Delete some to add more. Your existing marks are safe.' : 'You can add a few more.'}
      </p>
      {blocked && heavyPages.length > 0 ? (
        <div className="mt-2">
          <p className="text-sm font-medium">Pages with the most ink</p>
          <ul className="mt-1 flex flex-wrap gap-2">
            {heavyPages.map((p) => (
              <li key={p.page}>
                <button
                  type="button"
                  onClick={() => onGoToPage?.(p.page)}
                  className="inline-flex min-h-11 items-center rounded-full border border-input bg-card px-4 text-sm font-medium outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40"
                >
                  Page {p.page}: {p.drawings} {p.drawings === 1 ? 'drawing' : 'drawings'}, {inkSizeLabel(p.bytes)}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Alert>
  )
}
