import { Badge, Button, toast } from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import * as React from 'react'

import { useChosenSubjects } from '~/modules/coverage'

import * as api from '../api'
import { DisclaimerNote } from '../components/DisclaimerNote'
import { PlanBudgetForm } from '../components/PlanBudgetForm'
import { usePlanMutations, useSubjectStatuses } from '../hooks/usePaperAnalysis'
import type { PlanPreview } from '../types'

export function PlannerContainer() {
  const navigate = useNavigate()
  const { subjects: chosenSubjects } = useChosenSubjects()
  const { data: statusesData } = useSubjectStatuses()

  const subjects = React.useMemo(() => {
    const raw = statusesData?.subjects || []
    if (!chosenSubjects || chosenSubjects.length === 0) return raw
    const chosenMap = new Map(chosenSubjects.map((s) => [s.key, s]))
    const filtered = raw.filter((s) => chosenMap.has(s.subject_key))
    if (filtered.length > 0) {
      return filtered.map((s) => ({
        ...s,
        subject_name: s.subject_name || chosenMap.get(s.subject_key)?.name || s.subject_key,
      }))
    }
    return chosenSubjects.map((cs) => ({
      subject_key: cs.key,
      subject_name: cs.name,
      data_status: 'insufficient' as const,
      ranking: 'withheld' as const,
      papers_published: 0,
      papers_target: 6,
      days_left: null,
      seo_indexable: false,
    }))
  }, [statusesData?.subjects, chosenSubjects])

  const [days, setDays] = React.useState(14)
  const [hoursPerDay, setHoursPerDay] = React.useState(3.0)
  const [selectedSubjects, setSelectedSubjects] = React.useState<string[]>([])
  const [balanceSubjects, setBalanceSubjects] = React.useState(false)

  // Initialize selected subjects once subjects load
  React.useEffect(() => {
    if (subjects.length > 0 && selectedSubjects.length === 0) {
      setSelectedSubjects(subjects.map((s) => s.subject_key))
    }
  }, [subjects, selectedSubjects.length])

  const [preview, setPreview] = React.useState<PlanPreview | null>(null)
  const [isPreviewLoading, setIsPreviewLoading] = React.useState(false)

  const { adoptPlan, isAdopting } = usePlanMutations()

  const handleToggleSubject = (subjectKey: string) => {
    setSelectedSubjects((prev) =>
      prev.includes(subjectKey) ? prev.filter((k) => k !== subjectKey) : [...prev, subjectKey],
    )
  }

  const handleGeneratePreview = async () => {
    if (selectedSubjects.length === 0) return
    setIsPreviewLoading(true)
    try {
      const res = await api.previewPlan({
        days,
        hours_per_day: hoursPerDay,
        subject_keys: selectedSubjects,
        balance_subjects: balanceSubjects,
      })
      setPreview(res)
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Failed to generate plan preview.')
    } finally {
      setIsPreviewLoading(false)
    }
  }

  const handleAdopt = async () => {
    if (!preview) return
    try {
      const clientId = crypto.randomUUID()
      await adoptPlan({
        client_id: clientId,
        days,
        hours_per_day: hoursPerDay,
        subject_keys: selectedSubjects,
        balance_subjects: balanceSubjects,
      })
      toast.success('Revision plan adopted successfully!')
      navigate({ to: '/app/analysis/plan/active' })
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Could not adopt plan.')
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-6">
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Link to="/app/analysis" className="hover:underline">
            Analysis Hub
          </Link>
          <span>/</span>
          <span className="text-foreground">N-Days Planner</span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">If You Only Have N Days...</h1>
        <p className="text-sm text-muted-foreground">
          A pure greedy knapsack planner with a 2-approximation safeguard to maximize expected exam mark yield.
        </p>
      </div>

      <DisclaimerNote />

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
        {/* Left Form: Parameters */}
        <div className="lg:col-span-5">
          <PlanBudgetForm
            subjects={subjects}
            days={days}
            hoursPerDay={hoursPerDay}
            selectedSubjects={selectedSubjects}
            balanceSubjects={balanceSubjects}
            isLoading={isPreviewLoading}
            onChangeDays={setDays}
            onChangeHours={setHoursPerDay}
            onToggleSubject={handleToggleSubject}
            onChangeBalance={setBalanceSubjects}
            onSubmit={handleGeneratePreview}
          />
        </div>

        {/* Right Preview Output */}
        <div className="space-y-5 lg:col-span-7">
          {!preview ? (
            <div className="space-y-2 rounded-2xl border border-dashed bg-muted/20 p-12 text-center text-sm text-muted-foreground">
              <span className="block text-base font-semibold text-foreground">No Plan Preview Generated</span>
              <p>Configure your revision days and daily study hours, then click calculate.</p>
            </div>
          ) : (
            <div className="space-y-5">
              {/* Coverage Yield Card */}
              <div className="space-y-4 rounded-2xl border border-primary/30 bg-primary/5 p-5 shadow-xs">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="block font-mono text-xs font-semibold text-primary uppercase">
                      Historical Marks Yield
                    </span>
                    <span className="mt-0.5 block font-mono text-2xl font-bold text-foreground">
                      {Math.round(preview.covered_share * 100)}% of marks covered
                    </span>
                  </div>
                  <Button onClick={handleAdopt} disabled={isAdopting} size="default">
                    {isAdopting ? 'Adopting...' : 'Adopt This Plan'}
                  </Button>
                </div>

                {/* Honest Disclosure of Left-Out Share (PRD 7.5) */}
                <div className="flex items-center justify-between border-t border-primary/10 pt-3 text-xs text-muted-foreground">
                  <span>
                    Revision budget: <strong>{preview.hours_used}h</strong> of {preview.budget_hours}h usable
                  </span>
                  <span>
                    Excluded:{' '}
                    <strong>
                      {preview.left_out.chapters_n} chapters ({Math.round(preview.left_out.share * 100)}% of marks)
                    </strong>
                  </span>
                </div>
              </div>

              {/* Chosen Items Table */}
              <div className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
                <div className="flex items-center justify-between border-b border-border bg-muted/40 px-4 py-3">
                  <span className="text-xs font-semibold text-foreground">
                    Selected High-Yield Chapters ({preview.items.length})
                  </span>
                  <span className="font-mono text-[11px] text-muted-foreground">Ordered by expected marks / hour</span>
                </div>

                <div className="divide-y divide-border/60">
                  {preview.items.map((item, idx) => (
                    <div key={item.chapter_id} className="flex items-center justify-between gap-3 p-3.5 text-xs">
                      <div className="flex min-w-0 items-center gap-2.5">
                        <span className="font-mono font-semibold text-muted-foreground">#{idx + 1}</span>
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <span className="truncate font-medium text-foreground">{item.name}</span>
                            <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground uppercase">
                              {item.subject_key}
                            </span>
                            {item.mode === 'key_points' && (
                              <Badge
                                variant="outline"
                                className="h-4 border-amber-300 px-1.5 py-0 text-[10px] text-amber-700 dark:text-amber-300"
                              >
                                Key points
                              </Badge>
                            )}
                          </div>
                          <span className="mt-0.5 block text-[11px] text-muted-foreground">
                            Study time: {item.minutes} mins · Yield:{' '}
                            <strong className="text-foreground">+{item.expected_gain.toFixed(1)}m</strong>
                          </span>
                        </div>
                      </div>

                      <span className="shrink-0 font-mono text-xs font-semibold text-primary">
                        {item.mph.toFixed(1)} m/h
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
