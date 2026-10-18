import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  toast,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import * as React from 'react'

import { DisclaimerNote } from '../components/DisclaimerNote'
import { PlanTable } from '../components/PlanTable'
import { useActivePlan, usePlanMutations } from '../hooks/usePaperAnalysis'

export function ActivePlanContainer() {
  const navigate = useNavigate()
  const { data, isLoading } = useActivePlan()
  const plan = data?.plan

  const { updateItem, replan, endPlan, isReplanning } = usePlanMutations()

  const [isReplanOpen, setIsReplanOpen] = React.useState(false)
  const [replanDays, setReplanDays] = React.useState(7)
  const [replanHours, setReplanHours] = React.useState(3.0)

  const handleUpdateItem = async (itemId: string, state: 'planned' | 'done' | 'skipped') => {
    try {
      await updateItem({ itemId, state })
    } catch {
      toast.error('Failed to update task state.')
    }
  }

  const handleReplanSubmit = async () => {
    if (!plan) return
    try {
      await replan({
        days_remaining: replanDays,
        hours_per_day: replanHours,
      })
      toast.success('Plan replanned successfully!')
      setIsReplanOpen(false)
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Could not replan.')
    }
  }

  const handleEndPlan = async () => {
    if (!confirm('Are you sure you want to end your current revision plan?')) return
    try {
      await endPlan()
      toast.success('Revision plan ended.')
      navigate({ to: '/app/analysis' })
    } catch {
      toast.error('Failed to end plan.')
    }
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl space-y-4 p-6">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="h-32 animate-pulse rounded-xl bg-muted/40" />
      </div>
    )
  }

  if (!plan) {
    return (
      <div className="mx-auto max-w-2xl space-y-4 p-12 text-center">
        <h2 className="text-xl font-bold text-foreground">No Active Plan</h2>
        <p className="text-sm text-muted-foreground">
          You don't have an active revision plan running right now. Use the N-Days Planner to generate one.
        </p>
        <Button asChild>
          <Link to="/app/analysis/plan">Open N-Days Planner</Link>
        </Button>
      </div>
    )
  }

  const completedCount = plan.items.filter((it) => it.state === 'done').length
  const totalCount = plan.items.length
  const progressPct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Link to="/app/analysis" className="hover:underline">
              Analysis Hub
            </Link>
            <span>/</span>
            <span className="text-foreground">Active Plan</span>
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-foreground">Active Revision Plan</h1>
          <p className="text-xs text-muted-foreground">
            {plan.start_date} to {plan.end_date} · {plan.hours_per_day} hours/day
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setIsReplanOpen(true)}>
            Replan Schedule
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-destructive hover:bg-destructive/10"
            onClick={handleEndPlan}
          >
            End Plan
          </Button>
        </div>
      </div>

      <DisclaimerNote />

      {/* Progress Metric Card */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-card p-4">
        <div>
          <span className="block text-xs text-muted-foreground">Plan Progress</span>
          <span className="font-mono text-lg font-bold text-foreground">
            {completedCount} of {totalCount} chapters finished ({progressPct}%)
          </span>
        </div>
        <div className="text-right">
          <span className="block text-xs text-muted-foreground">Historical Marks Covered</span>
          <span className="font-mono text-lg font-bold text-primary">
            {Math.round(plan.summary.covered_share * 100)}%
          </span>
        </div>
      </div>

      {/* Daily Schedule */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold text-foreground">Daily Schedule</h2>
        <PlanTable items={plan.items} onUpdateItemState={handleUpdateItem} />
      </div>

      {/* Replan Dialog */}
      <Dialog open={isReplanOpen} onOpenChange={setIsReplanOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Replan Revision Schedule</DialogTitle>
            <DialogDescription>
              Adjust your remaining days and daily hours. Unfinished chapters will be redistributed automatically.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <label htmlFor="replan-days-input" className="text-xs font-medium text-foreground">
                Days remaining
              </label>
              <Input
                id="replan-days-input"
                type="number"
                min="1"
                max="60"
                value={replanDays}
                onChange={(e) => setReplanDays(parseInt(e.target.value) || 1)}
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="replan-hours-input" className="text-xs font-medium text-foreground">
                Hours per day
              </label>
              <Input
                id="replan-hours-input"
                type="number"
                step="0.5"
                min="1"
                max="12"
                value={replanHours}
                onChange={(e) => setReplanHours(parseFloat(e.target.value) || 1.0)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsReplanOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleReplanSubmit} disabled={isReplanning}>
              {isReplanning ? 'Replanning...' : 'Confirm Replan'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
