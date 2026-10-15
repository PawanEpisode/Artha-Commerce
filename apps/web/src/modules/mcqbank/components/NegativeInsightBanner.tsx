import { Alert, Badge, Card } from '@artha/design-system'

import type { NegativeInsightReport } from '../lib/types'

interface NegativeInsightBannerProps {
  report: NegativeInsightReport
  className?: string
}

export function NegativeInsightBanner({ report, className }: NegativeInsightBannerProps) {
  const hasPenalties = report.penalised_count > 0
  const guessStats = report.guess
  const sureStats = report.sure

  return (
    <Card className={`space-y-3 p-4 ${className ?? ''}`}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b pb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-foreground">Negative Marking Analysis</span>
          {report.break_even_pct !== null && (
            <Badge variant="outline" className="text-xs">
              Break-Even: {report.break_even_pct}%
            </Badge>
          )}
        </div>

        {hasPenalties ? (
          <span className="text-xs font-semibold text-destructive">
            -{report.total_penalties} marks lost ({report.penalised_count} penalised)
          </span>
        ) : (
          <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Zero penalties incurred!</span>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 text-xs sm:grid-cols-3">
        <div className="space-y-1 rounded-md border p-2.5">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Sure</span>
            <span className="font-medium">{sureStats.count} items</span>
          </div>
          <div className="text-sm font-semibold text-foreground">{sureStats.accuracy_pct}% acc.</div>
          <div className="text-muted-foreground">
            Net: {sureStats.net_marks > 0 ? `+${sureStats.net_marks}` : sureStats.net_marks}
          </div>
        </div>

        <div className="space-y-1 rounded-md border p-2.5">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Unsure</span>
            <span className="font-medium">{report.unsure.count} items</span>
          </div>
          <div className="text-sm font-semibold text-foreground">{report.unsure.accuracy_pct}% acc.</div>
          <div className="text-muted-foreground">
            Net: {report.unsure.net_marks > 0 ? `+${report.unsure.net_marks}` : report.unsure.net_marks}
          </div>
        </div>

        <div className="space-y-1 rounded-md border p-2.5">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Guesses</span>
            <span className="font-medium">{guessStats.count} items</span>
          </div>
          <div className="flex items-center gap-1.5 text-sm font-semibold">
            <span>{guessStats.accuracy_pct}% acc.</span>
            {guessStats.paying_off === true && (
              <Badge variant="outline" className="text-xs text-emerald-700 dark:text-emerald-300">
                Paid off
              </Badge>
            )}
            {guessStats.paying_off === false && (
              <Badge variant="outline" className="border-destructive/30 text-xs text-destructive">
                Costly
              </Badge>
            )}
          </div>
          <div className="text-muted-foreground">
            Net: {guessStats.net_marks > 0 ? `+${guessStats.net_marks}` : guessStats.net_marks}
          </div>
        </div>
      </div>

      {report.sure_but_wrong_count > 0 && (
        <Alert variant="error" className="py-2 text-xs">
          <strong>Review Warning:</strong> {report.sure_but_wrong_count} question(s) were marked &quot;Sure&quot; but
          answered incorrectly. Target these misconception areas before exam day.
        </Alert>
      )}
    </Card>
  )
}
