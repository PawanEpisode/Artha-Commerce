import { Card, Skeleton } from '@artha/design-system'

import type { SpeedData } from '../lib/types'

interface SpeedMatrixProps {
  data?: SpeedData
  isLoading?: boolean
}

export function SpeedMatrix({ data, isLoading }: SpeedMatrixProps) {
  if (isLoading || !data) {
    return <Skeleton className="h-48 w-full rounded-xl" />
  }

  const timed_answers_count = data.timed_answers_count ?? 0
  const pace = data.overall_pace_ratio ?? (data as unknown as { pace_ratio?: number }).pace_ratio ?? null
  const overall_pace_ratio = typeof pace === 'number' ? pace : null

  const quadrants = data.quadrants ?? {
    on_target: { count: 0, pct: 0 },
    slow_and_right: { count: 0, pct: 0 },
    fast_and_wrong: { count: 0, pct: 0 },
    slow_and_wrong: { count: 0, pct: 0 },
  }

  return (
    <Card className="space-y-4 p-5">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-text text-base font-semibold">Speed vs. Accuracy Quadrants</h3>
          <p className="text-text-subtle text-xs">Categorization against target suggested exam time limits</p>
        </div>
        <div className="text-right text-xs">
          <span className="text-text font-semibold">{timed_answers_count}</span>
          <span className="text-text-subtle"> timed questions</span>
          {typeof overall_pace_ratio === 'number' && (
            <div className="text-text-subtle">
              Avg Pace: <strong className="text-text">{overall_pace_ratio.toFixed(2)}x</strong> benchmark
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 pt-1 sm:grid-cols-2">
        {/* On Target */}
        <div className="space-y-1 rounded-lg border border-success/30 bg-success/5 p-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-success">On Target (Paced & Correct)</span>
            <span className="text-text font-bold">{quadrants.on_target?.pct ?? 0}%</span>
          </div>
          <p className="text-text-subtle text-[11px]">
            {quadrants.on_target?.count ?? 0} questions. Optimal exam tempo with high accuracy.
          </p>
        </div>

        {/* Slow & Right */}
        <div className="space-y-1 rounded-lg border border-info/30 bg-info/5 p-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-info">Slow & Right (Deliberate)</span>
            <span className="text-text font-bold">{quadrants.slow_and_right?.pct ?? 0}%</span>
          </div>
          <p className="text-text-subtle text-[11px]">
            {quadrants.slow_and_right?.count ?? 0} questions. Strong concepts; build confidence for speed.
          </p>
        </div>

        {/* Fast & Wrong */}
        <div className="space-y-1 rounded-lg border border-warning/30 bg-warning/5 p-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-warning">Fast & Wrong (Rushing)</span>
            <span className="text-text font-bold">{quadrants.fast_and_wrong?.pct ?? 0}%</span>
          </div>
          <p className="text-text-subtle text-[11px]">
            {quadrants.fast_and_wrong?.count ?? 0} questions. Likely misreading or guessing without checking.
          </p>
        </div>

        {/* Slow & Wrong */}
        <div className="border-danger/30 bg-danger/5 space-y-1 rounded-lg border p-3">
          <div className="flex items-center justify-between text-xs">
            <span className="text-danger font-semibold">Slow & Wrong (Struggling)</span>
            <span className="text-text font-bold">{quadrants.slow_and_wrong?.pct ?? 0}%</span>
          </div>
          <p className="text-text-subtle text-[11px]">
            {quadrants.slow_and_wrong?.count ?? 0} questions. Conceptual gap under time; prioritize basic revision.
          </p>
        </div>
      </div>
    </Card>
  )
}
