import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Card,
  CircleCheck,
  EmptyState,
  Skeleton,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  toast,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import * as React from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { CsvImportDialog } from '../components/CsvImportDialog'
import {
  type EditorReportItem,
  getEditorReports,
  getEditorReviewQueue,
  resolveEditorReport,
  type ReviewQueueItem,
} from '../lib/api'

export function EditorReviewQueueContainer() {
  const enabled = useFeatureFlag('question_bank', { strict: true })

  const [activeTab, setActiveTab] = React.useState('reviews')
  const [loading, setLoading] = React.useState(true)
  const [reviews, setReviews] = React.useState<ReviewQueueItem[]>([])
  const [reports, setReports] = React.useState<EditorReportItem[]>([])
  const [error, setError] = React.useState<string | null>(null)
  const [resolvingId, setResolvingId] = React.useState<string | null>(null)

  const loadData = React.useCallback(async () => {
    if (!enabled) return
    setLoading(true)
    setError(null)
    try {
      const [reviewItems, reportItems] = await Promise.all([
        getEditorReviewQueue('pending').catch(() => []),
        getEditorReports('open').catch(() => []),
      ])
      setReviews(reviewItems)
      setReports(reportItems)
    } catch {
      setError('Unable to load editorial queue.')
    } finally {
      setLoading(false)
    }
  }, [enabled])

  React.useEffect(() => {
    loadData()
  }, [loadData])

  const handleResolveReport = async (reportId: string, status: string) => {
    setResolvingId(reportId)
    try {
      await resolveEditorReport(reportId, { status, note: 'Actioned by editor' })
      toast.success(`Report marked as ${status}`)
      setReports((prev) => prev.filter((r) => r.id !== reportId))
    } catch {
      toast.error('Failed to update report.')
    } finally {
      setResolvingId(null)
    }
  }

  if (!enabled) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12">
        <Alert variant="info">The Question Bank editorial portal is not available.</Alert>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-8">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">Editorial Review & Quality</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Review submitted questions, manage student error reports, and bulk import content.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <CsvImportDialog onSuccess={() => loadData()} />
        </div>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="reviews" className="gap-2">
            Pending Submissions
            {reviews.length > 0 && (
              <Badge variant="default" className="px-1.5 py-0 text-xs">
                {reviews.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="reports" className="gap-2">
            Error Reports
            {reports.length > 0 && (
              <Badge variant="default" className="px-1.5 py-0 text-xs text-destructive">
                {reports.length}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="reviews" className="space-y-4 pt-4">
          {loading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-24 w-full" />
              ))}
            </div>
          ) : reviews.length === 0 ? (
            <EmptyState
              icon={<CircleCheck aria-hidden className="size-6 text-emerald-600" />}
              title="Editorial Queue is Clean"
              description="No questions are currently waiting for editorial review."
            />
          ) : (
            <div className="space-y-3">
              {reviews.map((item) => (
                <Card key={item.id} className="flex flex-col justify-between gap-4 p-4 sm:flex-row sm:items-center">
                  <div className="flex-1 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className="text-xs font-semibold">
                        {item.question_kind}
                      </Badge>
                      <Badge variant="default" className="text-xs">
                        {item.kind}
                      </Badge>
                      {item.sla_due_at && (
                        <span className="text-xs text-muted-foreground">
                          SLA: {new Date(item.sla_due_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    <p className="line-clamp-2 text-sm font-medium text-foreground">
                      {item.stem_head || 'Untitled Question'}
                    </p>
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <ButtonLink asChild variant="outline" size="sm">
                      <Link to="/app/questions/$id" params={{ id: item.question_id }}>
                        Review Question
                      </Link>
                    </ButtonLink>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="reports" className="space-y-4 pt-4">
          {loading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-24 w-full" />
              ))}
            </div>
          ) : reports.length === 0 ? (
            <EmptyState
              icon={<CircleCheck aria-hidden className="size-6 text-emerald-600" />}
              title="No Open Error Reports"
              description="All reported question issues have been resolved."
            />
          ) : (
            <div className="space-y-3">
              {reports.map((rep) => (
                <Card key={rep.id} className="flex flex-col justify-between gap-4 p-4 sm:flex-row sm:items-start">
                  <div className="flex-1 space-y-1.5">
                    <div className="flex items-center gap-2">
                      <Badge variant="default" className="text-xs text-destructive">
                        {rep.kind.replace('_', ' ')}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        Reported {new Date(rep.created_at).toLocaleDateString()}
                      </span>
                    </div>

                    <p className="text-sm font-medium text-foreground">&quot;{rep.message}&quot;</p>

                    <p className="line-clamp-1 text-xs text-muted-foreground">Question: {rep.stem_head}</p>
                  </div>

                  <div className="flex shrink-0 items-center gap-2 self-end sm:self-center">
                    <ButtonLink asChild variant="outline" size="sm">
                      <Link to="/app/questions/$id" params={{ id: rep.question_id }}>
                        View
                      </Link>
                    </ButtonLink>
                    <Button
                      size="sm"
                      onClick={() => handleResolveReport(rep.id, 'fixed')}
                      disabled={resolvingId === rep.id}
                    >
                      Mark Fixed
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
