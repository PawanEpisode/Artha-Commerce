import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  CircleCheck,
  DataTable,
  EmptyState,
  Page,
  PageHeader,
  Skeleton,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
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
import { kindLabel } from '../lib/labels'

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
      <Page width="form">
        <Alert variant="info">The Question Bank editorial portal is not available.</Alert>
      </Page>
    )
  }

  const skeleton = (
    <div role="status" aria-busy="true" aria-label="Loading queue" className="space-y-2">
      {[...Array(4)].map((_, i) => (
        <Skeleton key={i} className="h-9 w-full" />
      ))}
    </div>
  )

  return (
    <Page>
      <PageHeader
        title="Editorial Review & Quality"
        description="Review submitted questions, manage student error reports, and bulk import content."
        actions={<CsvImportDialog onSuccess={() => loadData()} />}
      />

      {error && <Alert variant="error">{error}</Alert>}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="reviews" className="gap-2">
            Pending Submissions
            {reviews.length > 0 && (
              <Badge variant="default" className="px-1.5 py-0">
                {reviews.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="reports" className="gap-2">
            Error Reports
            {reports.length > 0 && (
              <Badge variant="default" className="px-1.5 py-0 text-destructive">
                {reports.length}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="reviews" className="pt-3">
          {loading ? (
            skeleton
          ) : reviews.length === 0 ? (
            <EmptyState
              icon={<CircleCheck aria-hidden className="size-6 text-success-fg" />}
              title="Editorial Queue is Clean"
              description="No questions are currently waiting for editorial review."
            />
          ) : (
            <DataTable>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Question</TableHead>
                  <TableHead className="hidden sm:table-cell">Kind</TableHead>
                  <TableHead className="hidden sm:table-cell">Review</TableHead>
                  <TableHead className="hidden md:table-cell">SLA due</TableHead>
                  <TableHead className="text-right">
                    <span className="sr-only">Action</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reviews.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="min-w-48 py-2">
                      <p className="line-clamp-2 font-medium text-foreground">
                        {item.stem_head || 'Untitled Question'}
                      </p>
                    </TableCell>
                    <TableCell className="hidden sm:table-cell">
                      <Badge variant="outline">{kindLabel(item.question_kind)}</Badge>
                    </TableCell>
                    <TableCell className="hidden capitalize sm:table-cell">
                      <Badge variant="default">{item.kind.replace(/_/g, ' ')}</Badge>
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground tabular-nums md:table-cell">
                      {item.sla_due_at ? new Date(item.sla_due_at).toLocaleDateString() : '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      <ButtonLink asChild variant="outline" size="sm">
                        <Link to="/app/questions/$id" params={{ id: item.question_id }}>
                          Review Question
                        </Link>
                      </ButtonLink>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </DataTable>
          )}
        </TabsContent>

        <TabsContent value="reports" className="pt-3">
          {loading ? (
            skeleton
          ) : reports.length === 0 ? (
            <EmptyState
              icon={<CircleCheck aria-hidden className="size-6 text-success-fg" />}
              title="No Open Error Reports"
              description="All reported question issues have been resolved."
            />
          ) : (
            <DataTable>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Report</TableHead>
                  <TableHead className="hidden md:table-cell">Question</TableHead>
                  <TableHead className="hidden sm:table-cell">Reported</TableHead>
                  <TableHead className="text-right">
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reports.map((rep) => (
                  <TableRow key={rep.id}>
                    <TableCell className="min-w-48 py-2">
                      <Badge variant="default" className="text-destructive capitalize">
                        {rep.kind.replace(/_/g, ' ')}
                      </Badge>
                      <p className="mt-1 line-clamp-2 font-medium text-foreground">&quot;{rep.message}&quot;</p>
                    </TableCell>
                    <TableCell className="hidden max-w-64 text-muted-foreground md:table-cell">
                      <p className="line-clamp-2">{rep.stem_head}</p>
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground tabular-nums sm:table-cell">
                      {new Date(rep.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
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
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </DataTable>
          )}
        </TabsContent>
      </Tabs>
    </Page>
  )
}
