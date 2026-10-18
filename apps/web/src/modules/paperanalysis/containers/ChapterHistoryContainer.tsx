import { Button, TermStrip } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { DisclaimerNote } from '../components/DisclaimerNote'
import { useChapterHistory } from '../hooks/usePaperAnalysis'

export interface ChapterHistoryContainerProps {
  subjectKey: string
  chapterKey: string
}

export function ChapterHistoryContainer({ subjectKey, chapterKey }: ChapterHistoryContainerProps) {
  const { data, isLoading } = useChapterHistory(chapterKey, { window: 12 })
  const history = data?.history || []

  const sittings = history.map((s) => ({
    termCode: s.term_code,
    marks: s.marks_effective,
    isAsked: s.marks_effective > 0,
    paperKind: s.paper_kind,
  }))

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-6">
      {/* Breadcrumb Header */}
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Link to="/app/analysis" className="hover:underline">
            Analysis Hub
          </Link>
          <span>/</span>
          <Link to="/app/analysis/$subjectKey" params={{ subjectKey }} className="capitalize hover:underline">
            {subjectKey.replace('-', ' ')}
          </Link>
          <span>/</span>
          <span className="font-mono text-foreground uppercase">{chapterKey}</span>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-2xl font-bold tracking-tight text-foreground capitalize">
            {chapterKey.replace('-', ' ')}
          </h1>
          <Button asChild size="sm">
            <Link to="/app/practice">Start Practice</Link>
          </Button>
        </div>
      </div>

      <DisclaimerNote />

      {/* Sittings Strip */}
      {sittings.length > 0 && (
        <div className="space-y-2 rounded-xl border border-border bg-card p-4">
          <span className="block text-xs font-semibold text-foreground">Sitting-by-Sitting Frequency Strip</span>
          <TermStrip sittings={sittings} />
        </div>
      )}

      {/* History Breakdown Table */}
      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-border bg-muted/40 font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
              <tr>
                <th className="p-3">Sitting</th>
                <th className="p-3">Kind</th>
                <th className="p-3">Effective Marks</th>
                <th className="p-3">Total Offered</th>
                <th className="p-3">Questions</th>
                <th className="p-3">Theory / Practical</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="p-6 text-center text-muted-foreground">
                    Loading historical sittings...
                  </td>
                </tr>
              ) : history.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-6 text-center text-muted-foreground">
                    No past sittings recorded for this chapter.
                  </td>
                </tr>
              ) : (
                history.map((s, idx) => (
                  <tr key={`${s.term_code}-${idx}`} className="transition-colors hover:bg-muted/30">
                    <td className="p-3 font-mono font-medium text-foreground">{s.term_code}</td>
                    <td className="p-3 font-mono text-[11px] text-muted-foreground uppercase">{s.paper_kind}</td>
                    <td className="p-3 font-mono font-semibold text-foreground">
                      {s.marks_effective > 0 ? `${s.marks_effective.toFixed(1)}m` : '—'}
                    </td>
                    <td className="p-3 font-mono text-muted-foreground">
                      {s.marks_offered > 0 ? `${s.marks_offered.toFixed(1)}m` : '—'}
                    </td>
                    <td className="p-3 font-mono text-muted-foreground">
                      {s.question_count > 0 ? `${s.question_count} Qs` : '—'}
                    </td>
                    <td className="p-3 font-mono text-muted-foreground">
                      {s.marks_theory > 0 || s.marks_practical > 0 ? (
                        <span>
                          {s.marks_theory.toFixed(1)}m / {s.marks_practical.toFixed(1)}m
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
