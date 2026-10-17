import {
  Badge,
  Card,
  ProgressBar,
  SegmentedControl,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'

import type { GroupByOption, PerformanceData, RangeWindow } from '../lib/types'

interface PerformanceTableProps {
  data?: PerformanceData
  isLoading?: boolean
  groupBy: GroupByOption
  onGroupByChange: (by: GroupByOption) => void
  range: RangeWindow
  onRangeChange: (r: RangeWindow) => void
}

export function PerformanceTable({
  data,
  isLoading,
  groupBy,
  onGroupByChange,
  range,
  onRangeChange,
}: PerformanceTableProps) {
  const groupOptions: ReadonlyArray<{ value: GroupByOption; label: string }> = [
    { value: 'chapter', label: 'Chapter' },
    { value: 'difficulty', label: 'Difficulty' },
    { value: 'kind', label: 'Question Kind' },
    { value: 'source', label: 'Source' },
  ]

  const rangeOptions: ReadonlyArray<{ value: RangeWindow; label: string }> = [
    { value: '7d', label: '7 Days' },
    { value: '30d', label: '30 Days' },
    { value: '90d', label: '90 Days' },
    { value: 'all', label: 'All Time' },
  ]

  const renderStatus = (acc: number, answered: number) => {
    if (answered < 5) return <Badge variant="outline">New</Badge>
    if (acc >= 75) return <Badge variant="accent">Mastered</Badge>
    if (acc >= 55) return <Badge variant="default">Practicing</Badge>
    return <Badge variant="highlight">Struggling</Badge>
  }

  return (
    <Card className="space-y-4 p-5">
      <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h3 className="text-text text-base font-semibold">Performance Explorer</h3>
          <p className="text-text-subtle text-xs">Empirical Bayes shrunk mastery & Wilson 95% confidence intervals</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SegmentedControl
            label="Group by category"
            value={groupBy}
            onValueChange={onGroupByChange}
            options={groupOptions}
          />
          <SegmentedControl
            label="Date range window"
            value={range}
            onValueChange={onRangeChange}
            options={rangeOptions}
          />
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2 py-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="text-text-subtle py-10 text-center text-sm">
          No practice attempts found for this window and category.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Category / Name</TableHead>
                <TableHead className="text-right">Questions</TableHead>
                <TableHead className="text-right">Raw Accuracy</TableHead>
                <TableHead className="text-right">Shrunk Mastery</TableHead>
                <TableHead className="text-right">Wilson 95% Band</TableHead>
                <TableHead className="text-right">Pace</TableHead>
                <TableHead className="text-center">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((item, idx) => {
                const key = item.key || item.chapter_id || item.group_key || `row-${idx}`
                const label = item.label || item.chapter_name || item.group_name || 'Item'
                const accPct = item.accuracy_pct ?? Math.round((item.accuracy ?? 0) * 100)
                const shrunkPct = item.shrunk_accuracy_pct ?? accPct
                const wilsonLow = item.wilson_low_pct ?? 0
                const wilsonHigh = item.wilson_high_pct ?? 0
                const pace = typeof item.avg_pace_ratio === 'number' ? item.avg_pace_ratio : null

                return (
                  <TableRow key={key}>
                    <TableCell className="text-text font-medium">{label}</TableCell>
                    <TableCell className="text-right">
                      {item.answered} ({item.correct} correct)
                    </TableCell>
                    <TableCell className="text-right">
                      <span className="font-semibold">{accPct}%</span>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <ProgressBar value={shrunkPct} label={`${label} mastery`} size="sm" className="w-16" />
                        <span className="text-text-subtle text-xs">{shrunkPct}%</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-text-subtle text-right text-xs">
                      [{wilsonLow}% – {wilsonHigh}%]
                    </TableCell>
                    <TableCell className="text-right text-xs">{pace !== null ? `${pace.toFixed(2)}x` : '—'}</TableCell>
                    <TableCell className="text-center">{renderStatus(accPct, item.answered)}</TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </Card>
  )
}
