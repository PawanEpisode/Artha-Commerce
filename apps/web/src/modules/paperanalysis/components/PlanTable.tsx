import { Badge, Button, Checkbox } from '@artha/design-system'

import type { PlanItem } from '../types'

export interface PlanTableProps {
  items: PlanItem[]
  onUpdateItemState?: (itemId: string, newState: 'planned' | 'done' | 'skipped') => void
  readOnly?: boolean
}

export function PlanTable({ items, onUpdateItemState, readOnly = false }: PlanTableProps) {
  if (!items || items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
        No revision items planned for this period.
      </div>
    )
  }

  // Group items by planned_date
  const grouped = items.reduce<Record<string, PlanItem[]>>((acc, item) => {
    const d = item.planned_date || 'Unscheduled'
    if (!acc[d]) acc[d] = []
    acc[d].push(item)
    return acc
  }, {})

  const dates = Object.keys(grouped).sort()

  return (
    <div className="space-y-6">
      {dates.map((dateStr) => {
        const dayItems = grouped[dateStr]
        const totalMinutes = dayItems.reduce((acc, it) => acc + it.minutes, 0)
        const totalHours = (totalMinutes / 60).toFixed(1)

        return (
          <div key={dateStr} className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
            {/* Day Header */}
            <div className="flex items-center justify-between border-b border-border bg-muted/40 px-4 py-2.5">
              <span className="text-xs font-semibold tracking-tight text-foreground">{dateStr}</span>
              <span className="font-mono text-[11px] text-muted-foreground">
                {dayItems.length} tasks · {totalHours}h
              </span>
            </div>

            {/* Day Items */}
            <div className="divide-y divide-border/60">
              {dayItems.map((item) => {
                const isDone = item.state === 'done'
                const isSkipped = item.state === 'skipped'

                return (
                  <div
                    key={item.id}
                    className={`flex items-center justify-between gap-3 p-3.5 transition-colors ${
                      isDone ? 'bg-emerald-50/20 dark:bg-emerald-950/10' : ''
                    } ${isSkipped ? 'line-through opacity-50' : ''}`}
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      {!readOnly && onUpdateItemState && (
                        <Checkbox
                          checked={isDone}
                          onCheckedChange={(checked) => {
                            onUpdateItemState(item.id, checked ? 'done' : 'planned')
                          }}
                          aria-label={`Mark ${item.chapter_key} done`}
                        />
                      )}

                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`truncate text-sm font-medium ${
                              isDone ? 'font-semibold text-emerald-700 dark:text-emerald-300' : 'text-foreground'
                            }`}
                          >
                            {item.chapter_key}
                          </span>
                          <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                            {item.subject_key}
                          </span>
                          {item.mode === 'key_points' && (
                            <Badge
                              variant="outline"
                              className="h-4 border-amber-300 px-1.5 py-0 text-[10px] text-amber-700 dark:text-amber-300"
                            >
                              Key points only
                            </Badge>
                          )}
                        </div>

                        <div className="mt-0.5 flex items-center gap-3 text-xs text-muted-foreground">
                          <span>{item.minutes} mins</span>
                          <span>·</span>
                          <span>
                            Yield:{' '}
                            <strong className="font-mono text-foreground">+{item.expected_gain.toFixed(1)}m</strong>
                          </span>
                        </div>
                      </div>
                    </div>

                    {!readOnly && onUpdateItemState && (
                      <div className="flex shrink-0 items-center gap-1">
                        {item.state !== 'skipped' ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-xs text-muted-foreground hover:text-destructive"
                            onClick={() => onUpdateItemState(item.id, 'skipped')}
                          >
                            Skip
                          </Button>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-xs text-muted-foreground hover:text-primary"
                            onClick={() => onUpdateItemState(item.id, 'planned')}
                          >
                            Restore
                          </Button>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
