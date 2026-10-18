import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Skeleton,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { DisclaimerNote } from '../components/DisclaimerNote'
import { useActivePlan, useSubjectStatuses } from '../hooks/usePaperAnalysis'
import type { SubjectStatus } from '../types'

export function AnalysisHubContainer() {
  const { data: statusesData, isLoading: isLoadingSubjects } = useSubjectStatuses()
  const { data: activePlanData, isLoading: isLoadingPlan } = useActivePlan()

  const subjects = statusesData?.subjects || []
  const activePlan = activePlanData?.plan

  const statusBadge = (status: SubjectStatus['data_status']) => {
    switch (status) {
      case 'ready':
        return <Badge variant="default">Ready</Badge>
      case 'limited':
        return <Badge variant="accent">Limited data</Badge>
      case 'withheld':
        return (
          <Badge variant="outline" className="border-destructive/30 text-destructive">
            Ranking withheld
          </Badge>
        )
      default:
        return <Badge variant="outline">Insufficient data</Badge>
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 p-4 md:p-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Paper Analysis & Recommendations</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Historical exam patterns, priority chapter weightages, and high-yield study planning.
          </p>
        </div>

        <Button asChild size="default">
          <Link to="/app/analysis/plan">{activePlan ? 'View / Adjust Plan' : 'Create Revision Plan'}</Link>
        </Button>
      </div>

      {/* Standing Disclaimer */}
      <DisclaimerNote />

      {/* Active Plan Spotlight */}
      {!isLoadingPlan && activePlan && (
        <Card className="border-primary/30 bg-primary/5">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs font-semibold tracking-wider text-primary uppercase">
                Active Study Plan
              </span>
              <Badge variant="default">In progress</Badge>
            </div>
            <CardTitle className="text-lg">{activePlan.days}-Day Revision Schedule</CardTitle>
            <CardDescription>
              {activePlan.hours_per_day} hours/day · {activePlan.summary.items_count} planned chapter sessions
            </CardDescription>
          </CardHeader>
          <CardContent className="flex items-center justify-between pt-0">
            <div className="text-xs text-muted-foreground">
              Historically covers <strong>{Math.round(activePlan.summary.covered_share * 100)}%</strong> of exam marks.
            </div>
            <Button size="sm" asChild>
              <Link to="/app/analysis/plan/active">Open Today's Tasks</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Enrolled Subjects Grid */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-foreground">Your Subjects</h2>

        {isLoadingSubjects ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Skeleton className="h-36 rounded-xl" />
            <Skeleton className="h-36 rounded-xl" />
          </div>
        ) : subjects.length === 0 ? (
          <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
            No active subject enrollments found.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {subjects.map((sub) => (
              <Card
                key={sub.subject_key}
                className="flex flex-col justify-between transition-colors hover:border-primary/50"
              >
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs text-muted-foreground uppercase">{sub.subject_key}</span>
                    {statusBadge(sub.data_status)}
                  </div>
                  <CardTitle className="mt-1 text-base text-foreground">
                    {sub.subject_name || sub.subject_key}
                  </CardTitle>
                  <CardDescription>
                    {sub.papers_published} exam sittings analysed (target: {sub.papers_target})
                    {sub.days_left !== null && ` · ${sub.days_left} days until exam`}
                  </CardDescription>
                </CardHeader>

                <CardContent className="pt-0">
                  <div className="flex items-center justify-end gap-2">
                    <Button variant="outline" size="sm" asChild>
                      <Link to="/app/analysis/$subjectKey" params={{ subjectKey: sub.subject_key }}>
                        Explore Analysis
                      </Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
