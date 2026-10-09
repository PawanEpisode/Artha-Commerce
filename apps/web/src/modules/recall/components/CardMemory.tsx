import { StatTile } from '@artha/design-system'

import { percent, plural, shortDate } from '../lib/format'
import { DEFAULT_WEIGHTS, retrievability } from '../lib/fsrs6'
import type { CardMemory as Memory, ReviewRow } from '../lib/schemas'

const day = (iso: string) => shortDate(iso.slice(0, 10))
const RATINGS: Record<number, string> = { 1: 'Again', 2: 'Hard', 3: 'Good', 4: 'Easy' }

/** Her memory of one card in plain words: how long it lasts, how hard it is, how likely she recalls it now. */
export function CardMemoryPanel({ memory, now = new Date() }: { memory: Memory; now?: Date }) {
  if (memory.reps === 0 || memory.stability === null) {
    return <p className="text-sm text-muted-foreground">You have not reviewed this card yet.</p>
  }
  const w20 = DEFAULT_WEIGHTS[20] ?? 0.1542
  const elapsed = memory.last_review_at ? (now.getTime() - new Date(memory.last_review_at).getTime()) / 86_400_000 : 0
  const recall = retrievability(memory.stability, elapsed, w20)
  return (
    <div role="group" aria-label="Your memory of this card" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <StatTile label="Likely to recall now" value={percent(recall)} />
      <StatTile label="Lasts about" value={plural(Math.max(1, Math.round(memory.stability)), 'day')} />
      <StatTile label="Difficulty" value={memory.difficulty === null ? '-' : `${memory.difficulty.toFixed(1)} of 10`} />
      <StatTile label="Next review" value={memory.due_at ? day(memory.due_at) : '-'} />
    </div>
  )
}

export function ReviewHistory({ rows }: { rows: readonly ReviewRow[] }) {
  if (rows.length === 0) return <p className="text-sm text-muted-foreground">No reviews yet.</p>
  return (
    <ol className="divide-y divide-border rounded-xl border border-border">
      {rows.map((r) => (
        <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 text-sm">
          <span className="font-medium">{r.rating ? (RATINGS[r.rating] ?? 'Rated') : 'Rated'}</span>
          <span className="text-muted-foreground">
            {day(r.reviewed_at)}
            {r.scheduled_days !== null && r.scheduled_days >= 1
              ? `, next in ${plural(Math.round(r.scheduled_days), 'day')}`
              : ''}
          </span>
        </li>
      ))}
    </ol>
  )
}
