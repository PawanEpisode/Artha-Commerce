import { Badge } from '@artha/design-system'

import { formatDuration } from '../lib/duration'
import type { TimeVsCoverage } from '../lib/types'

const FLAG_TEXT: Record<string, string> = {
  high_time_low_coverage: 'Lots of time, little covered',
  low_time_low_coverage: 'Little time and little covered',
}

/** Time spent against coverage for each chapter of one subject. A flag is a word, never only a colour. */
export function TimeVsCoverageTable({ data }: { data: TimeVsCoverage }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[32rem] text-left text-sm">
        <caption className="sr-only">Time spent and coverage by chapter for {data.subject.name}</caption>
        <thead>
          <tr className="border-b border-border">
            <th scope="col" className="py-2 pr-3 font-semibold">
              Chapter
            </th>
            <th scope="col" className="py-2 pr-3 font-semibold">
              Time
            </th>
            <th scope="col" className="py-2 pr-3 font-semibold">
              Covered
            </th>
            <th scope="col" className="py-2 font-semibold">
              Note
            </th>
          </tr>
        </thead>
        <tbody>
          {data.chapters.map((c) => (
            <tr key={c.chapter_id} className="border-b border-border last:border-0">
              <th scope="row" className="py-2 pr-3 font-medium">
                {c.name}
              </th>
              <td className="py-2 pr-3 tabular-nums">{formatDuration(c.seconds)}</td>
              <td className="py-2 pr-3 tabular-nums">{Math.round(c.coverage_percent)}%</td>
              <td className="py-2">
                {c.flag ? <Badge variant="highlight">{FLAG_TEXT[c.flag] ?? c.flag}</Badge> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
