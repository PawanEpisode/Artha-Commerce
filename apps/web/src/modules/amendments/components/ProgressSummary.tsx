import { Card, ProgressBar } from '@artha/design-system'

import type { MySummary } from '../lib/types'

interface Props {
  summary: MySummary
  onSelectSubject?: (subjectKey: string) => void
  activeSubject?: string
  className?: string
}

export function ProgressSummary({ summary, onSelectSubject, activeSubject, className }: Props) {
  const { total_cards_count, reviewed_count, target_term, breakdown_by_paper } = summary
  const pct = total_cards_count > 0 ? Math.round((reviewed_count / total_cards_count) * 100) : 0

  return (
    <Card className={className}>
      <div className="p-4 sm:p-5">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold sm:text-lg">
              {target_term ? `Amendments for ${target_term}` : 'My Amendments'}
            </h2>
            <p className="text-xs text-muted-foreground sm:text-sm">
              {total_cards_count === 0
                ? 'No live amendments found for your attempt.'
                : `${total_cards_count} changes apply to your papers. Reviewed ${reviewed_count} of ${total_cards_count} (${pct}%).`}
            </p>
          </div>
          <div className="mt-2 text-xs font-medium text-muted-foreground sm:mt-0 sm:text-right">Progress: {pct}%</div>
        </div>

        <div className="mt-3">
          <ProgressBar value={pct} label="Amendments reviewed progress" className="h-2" />
        </div>

        {breakdown_by_paper.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2 border-t pt-3">
            <button
              type="button"
              onClick={() => onSelectSubject?.('')}
              className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                !activeSubject
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              }`}
            >
              All papers ({total_cards_count})
            </button>
            {breakdown_by_paper.map((p) => {
              const isSelected = activeSubject === p.subject_key
              return (
                <button
                  key={p.subject_key}
                  type="button"
                  onClick={() => onSelectSubject?.(p.subject_key)}
                  className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                    isSelected
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground hover:bg-muted/80'
                  }`}
                >
                  {p.subject_key} ({p.reviewed}/{p.total})
                </button>
              )
            })}
          </div>
        )}
      </div>
    </Card>
  )
}
