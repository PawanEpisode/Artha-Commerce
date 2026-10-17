import {
  Badge,
  Button,
  Card,
  Checkbox,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  Label,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import * as React from 'react'

import { useCreateReport, useReports } from '../hooks/useAnalytics'
import { ShareModal } from './ShareModal'

export function ReportsView() {
  const { data, isLoading } = useReports()
  const { mutate: createReport, isPending: isCreating } = useCreateReport()

  const [createModalOpen, setCreateModalOpen] = React.useState(false)
  const [shareReportId, setShareReportId] = React.useState<string | null>(null)
  const [shareModalOpen, setShareModalOpen] = React.useState(false)

  const [periodKind, setPeriodKind] = React.useState('30d')
  const [includeName, setIncludeName] = React.useState(true)
  const [includeMistakes, setIncludeMistakes] = React.useState(true)
  const [includeTime, setIncludeTime] = React.useState(true)

  const handleCreate = () => {
    createReport(
      {
        period_kind: periodKind,
        include_name: includeName,
        include_mistakes: includeMistakes,
        include_time: includeTime,
      },
      {
        onSuccess: () => {
          setCreateModalOpen(false)
        },
      },
    )
  }

  const handleOpenShare = (reportId: string) => {
    setShareReportId(reportId)
    setShareModalOpen(true)
  }

  const reports = data?.items ?? []

  return (
    <>
      <Card className="space-y-4 p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-text text-base font-semibold">Progress Reports & Sharing</h3>
            <p className="text-text-subtle text-xs">
              Freeze readiness snapshots and create secure share links for mentors
            </p>
          </div>
          <Button size="sm" variant="default" onClick={() => setCreateModalOpen(true)}>
            Generate Report
          </Button>
        </div>

        {isLoading ? (
          <div className="space-y-2 py-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : reports.length === 0 ? (
          <div className="text-text-subtle py-8 text-center text-xs">
            No progress reports created yet. Generate one to view or share your historical snapshot.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Period</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Date Range</TableHead>
                  <TableHead>Expires</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reports.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="text-text text-xs font-medium uppercase">{r.period_kind}</TableCell>
                    <TableCell>
                      <Badge variant={r.status === 'ready' ? 'accent' : 'outline'}>{r.status}</Badge>
                    </TableCell>
                    <TableCell className="text-text-subtle text-xs">
                      {r.from_date} to {r.to_date}
                    </TableCell>
                    <TableCell className="text-text-subtle text-xs">
                      {r.expires_at ? new Date(r.expires_at).toLocaleDateString() : '—'}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="secondary" className="text-xs" onClick={() => handleOpenShare(r.id)}>
                        Share
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Card>

      {/* Generate Report Dialog */}
      <Dialog open={createModalOpen} onOpenChange={setCreateModalOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Generate Progress Report</DialogTitle>
            <DialogDescription>Create a frozen audit report of your practice and readiness metrics.</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 pt-2 text-xs">
            <div className="space-y-1.5">
              <Label htmlFor="report-period-select" className="text-text font-semibold">
                Time Period:
              </Label>
              <select
                id="report-period-select"
                value={periodKind}
                onChange={(e) => setPeriodKind(e.target.value)}
                className="flex h-8 w-full rounded-md border border-input bg-card px-2.5 text-xs text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
              >
                <option value="7d">Last 7 Days</option>
                <option value="30d">Last 30 Days</option>
                <option value="90d">Last 90 Days</option>
                <option value="all">All History</option>
              </select>
            </div>

            <div className="space-y-2 border-t pt-2">
              <span className="text-text font-semibold">Privacy & Inclusions:</span>
              <div className="flex items-center gap-2">
                <Checkbox
                  id="report-inc-name"
                  checked={includeName}
                  onCheckedChange={(c) => setIncludeName(Boolean(c))}
                />
                <Label htmlFor="report-inc-name" className="cursor-pointer">
                  Include my student name on the share page
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <Checkbox
                  id="report-inc-mistakes"
                  checked={includeMistakes}
                  onCheckedChange={(c) => setIncludeMistakes(Boolean(c))}
                />
                <Label htmlFor="report-inc-mistakes" className="cursor-pointer">
                  Include mistake pattern breakdown
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <Checkbox
                  id="report-inc-time"
                  checked={includeTime}
                  onCheckedChange={(c) => setIncludeTime(Boolean(c))}
                />
                <Label htmlFor="report-inc-time" className="cursor-pointer">
                  Include study time totals
                </Label>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setCreateModalOpen(false)}>
                Cancel
              </Button>
              <Button variant="default" onClick={handleCreate} loading={isCreating}>
                Generate
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <ShareModal reportId={shareReportId} open={shareModalOpen} onOpenChange={setShareModalOpen} />
    </>
  )
}
