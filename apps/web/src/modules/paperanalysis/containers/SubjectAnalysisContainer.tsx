import { ConfidenceBadge, Tabs, TabsContent, TabsList, TabsTrigger } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import * as React from 'react'

import { useChosenSubjects } from '~/modules/coverage'

import { DisclaimerNote } from '../components/DisclaimerNote'
import { TierGroup } from '../components/TierGroup'
import { usePriority, useSubjectPatterns, useSubjectStats } from '../hooks/usePaperAnalysis'

export interface SubjectAnalysisContainerProps {
  subjectKey: string
  initialTab?: string
}

export function SubjectAnalysisContainer({ subjectKey, initialTab = 'priority' }: SubjectAnalysisContainerProps) {
  const [tab, setTab] = React.useState(initialTab)
  const [windowSize, setWindowSize] = React.useState(6)

  const { subjects: chosenSubjects } = useChosenSubjects()
  const chosenSubject = chosenSubjects.find((s) => s.key === subjectKey)

  const { data: priorityView, isLoading: isLoadingPriority } = usePriority({
    subjectKey,
  })
  const { data: statsData, isLoading: isLoadingStats } = useSubjectStats(subjectKey, { window: windowSize })
  const { data: patternsData, isLoading: isLoadingPatterns } = useSubjectPatterns(subjectKey, { window: windowSize })

  const subjectPriority = priorityView?.subjects?.find((s) => s.subject_key === subjectKey)

  const coreChapters = subjectPriority?.chapters?.filter((c) => c.tier === 'core') || []
  const nextChapters = subjectPriority?.chapters?.filter((c) => c.tier === 'next') || []
  const restChapters = subjectPriority?.chapters?.filter((c) => c.tier === 'rest') || []

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-6">
      {/* Header */}
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Link to="/app/analysis" className="hover:underline">
            Analysis Hub
          </Link>
          <span>/</span>
          <span className="font-mono text-foreground uppercase">{subjectKey}</span>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            {chosenSubject?.name || subjectKey.replace(/-/g, ' ')}
          </h1>
          {subjectPriority && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-foreground">
                Based on {subjectPriority.papers_considered} past sittings
              </span>
              <ConfidenceBadge level={subjectPriority.confidence} />
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={tab} onValueChange={setTab} className="w-full">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-2">
          <TabsList>
            <TabsTrigger value="priority">Priority Ranking</TabsTrigger>
            <TabsTrigger value="chapters">Chapter Statistics</TabsTrigger>
            <TabsTrigger value="patterns">Paper Patterns</TabsTrigger>
          </TabsList>

          {/* Window size controls */}
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span>Window:</span>
            {[6, 10, 12].map((w) => (
              <button
                key={w}
                type="button"
                onClick={() => setWindowSize(w)}
                className={`rounded px-2 py-0.5 font-mono text-xs transition-colors ${
                  windowSize === w
                    ? 'bg-primary font-semibold text-primary-foreground'
                    : 'bg-muted text-foreground hover:bg-muted/80'
                }`}
              >
                {w} sittings
              </button>
            ))}
          </div>
        </div>

        {/* 1. Priority Tab */}
        <TabsContent value="priority" className="space-y-5 pt-4">
          <DisclaimerNote />

          {isLoadingPriority ? (
            <div className="space-y-3">
              <div className="h-28 animate-pulse rounded-xl bg-muted/40" />
              <div className="h-28 animate-pulse rounded-xl bg-muted/40" />
            </div>
          ) : !subjectPriority ? (
            <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
              No priority recommendations available for this subject yet.
            </div>
          ) : subjectPriority.ranking === 'withheld' ? (
            <div className="space-y-2 rounded-xl border border-amber-300 bg-amber-50/50 p-6 text-amber-900 dark:bg-amber-950/20 dark:text-amber-200">
              <h3 className="text-sm font-semibold">Ranking temporarily withheld</h3>
              <p className="text-xs">
                Fewer than the minimum number of official exam papers have been published or verified for this subject.
                Individual chapter frequencies remain accessible in the statistics tab.
              </p>
            </div>
          ) : (
            <div className="space-y-5">
              <TierGroup
                tier="core"
                title="Core Chapters"
                description="Carries approximately 50% of historical exam marks"
                chapters={coreChapters}
                subjectKey={subjectKey}
                defaultOpen={true}
              />

              <TierGroup
                tier="next"
                title="Next Chapters"
                description="Carries up to 80% of cumulative historical marks"
                chapters={nextChapters}
                subjectKey={subjectKey}
                defaultOpen={true}
              />

              <TierGroup
                tier="rest"
                title="Lower Expected Weight"
                description="Remaining chapters with lower historical frequency"
                chapters={restChapters}
                subjectKey={subjectKey}
                defaultOpen={false}
              />
            </div>
          )}
        </TabsContent>

        {/* 2. Chapter Statistics Tab */}
        <TabsContent value="chapters" className="space-y-4 pt-4">
          <div className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-border bg-muted/40 font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                  <tr>
                    <th className="p-3">Chapter</th>
                    <th className="p-3">Asked Frequency</th>
                    <th className="p-3">Avg Effective Marks</th>
                    <th className="p-3">Max in Sitting</th>
                    <th className="p-3">Trend</th>
                    <th className="p-3 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {isLoadingStats ? (
                    <tr>
                      <td colSpan={6} className="p-6 text-center text-muted-foreground">
                        Loading statistics...
                      </td>
                    </tr>
                  ) : !statsData?.chapters || statsData.chapters.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="p-6 text-center text-muted-foreground">
                        No chapter statistics computed for this window.
                      </td>
                    </tr>
                  ) : (
                    statsData.chapters.map((ch) => (
                      <tr key={ch.chapter_id} className="transition-colors hover:bg-muted/30">
                        <td className="p-3 font-medium text-foreground">{ch.name}</td>
                        <td className="p-3 font-mono">
                          {ch.asked_n} / {ch.papers_considered} sittings
                        </td>
                        <td className="p-3 font-mono font-semibold text-foreground">{ch.avg_effective.toFixed(1)}m</td>
                        <td className="p-3 font-mono text-muted-foreground">
                          {ch.max_effective !== null ? `${ch.max_effective.toFixed(1)}m` : '—'}
                        </td>
                        <td className="p-3 font-mono">
                          {ch.trend !== null ? (
                            <span
                              className={
                                ch.trend > 0
                                  ? 'font-semibold text-emerald-600 dark:text-emerald-400'
                                  : ch.trend < 0
                                    ? 'text-amber-600 dark:text-amber-400'
                                    : 'text-muted-foreground'
                              }
                            >
                              {ch.trend > 0 ? `+${ch.trend.toFixed(2)}` : ch.trend.toFixed(2)}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="p-3 text-right">
                          <Link
                            to="/app/analysis/$subjectKey/$chapterKey"
                            params={{ subjectKey, chapterKey: ch.chapter_key }}
                            className="font-medium text-primary hover:underline"
                          >
                            History →
                          </Link>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </TabsContent>

        {/* 3. Paper Patterns Tab */}
        <TabsContent value="patterns" className="space-y-5 pt-4">
          {isLoadingPatterns ? (
            <div className="h-32 animate-pulse rounded-xl bg-muted/40" />
          ) : !patternsData ? (
            <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
              No pattern data recorded.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="rounded-xl border border-border bg-card p-4">
                <span className="block text-xs text-muted-foreground">Average Paper Marks</span>
                <span className="mt-1 block font-mono text-2xl font-bold text-foreground">
                  {patternsData.avg_total_marks.toFixed(1)}m
                </span>
                <span className="mt-1 block text-[11px] text-muted-foreground">
                  Across {patternsData.papers_considered} analysed papers
                </span>
              </div>

              <div className="rounded-xl border border-border bg-card p-4">
                <span className="block text-xs text-muted-foreground">Attemptable Marks</span>
                <span className="mt-1 block font-mono text-2xl font-bold text-primary">
                  {patternsData.avg_attemptable_marks.toFixed(1)}m
                </span>
                <span className="mt-1 block text-[11px] text-muted-foreground">Maximum possible score</span>
              </div>

              <div className="rounded-xl border border-border bg-card p-4">
                <span className="block text-xs text-muted-foreground">Optional Choice Offered</span>
                <span className="mt-1 block font-mono text-2xl font-bold text-muted-foreground">
                  {patternsData.avg_optional_marks.toFixed(1)}m
                </span>
                <span className="mt-1 block text-[11px] text-muted-foreground">Internal options & alternatives</span>
              </div>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
