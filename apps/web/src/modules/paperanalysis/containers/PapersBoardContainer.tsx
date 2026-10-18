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
import * as React from 'react'

import * as api from '../api'
import { PaperProgressBoard, type PaperSummaryItem } from '../components/PaperProgressBoard'

export function PapersBoardContainer() {
  const [papers, setPapers] = React.useState<PaperSummaryItem[]>([])
  const [isLoading, setIsLoading] = React.useState(true)

  const [isCreateOpen, setIsCreateOpen] = React.useState(false)
  const [termCode, setTermCode] = React.useState('2026-05')
  const [paperKind, setPaperKind] = React.useState('exam')
  const [totalMarks, setTotalMarks] = React.useState(100)
  const [subjectId, setSubjectId] = React.useState('')
  const [isCreating, setIsCreating] = React.useState(false)

  const loadPapers = React.useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await api.fetchEditorialPapers()
      setPapers((res.papers as unknown as PaperSummaryItem[]) || [])
    } catch {
      toast.error('Failed to load editorial papers.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  React.useEffect(() => {
    loadPapers()
  }, [loadPapers])

  const handleCreatePaper = async () => {
    if (!termCode || !subjectId) {
      toast.error('Please specify Subject ID and Term code.')
      return
    }
    setIsCreating(true)
    try {
      await api.createEditorialPaper({
        subject_id: subjectId,
        term_code: termCode,
        paper_kind: paperKind,
        total_marks: totalMarks,
      })
      toast.success('Paper created successfully!')
      setIsCreateOpen(false)
      loadPapers()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Could not create paper.')
    } finally {
      setIsCreating(false)
    }
  }

  const handlePublish = async (paperId: string) => {
    try {
      await api.publishPaper(paperId)
      toast.success('Paper published!')
      loadPapers()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Failed to publish paper.')
    }
  }

  const handleUnpublish = async (paperId: string) => {
    try {
      await api.unpublishPaper(paperId, 'Editor retracted paper')
      toast.success('Paper unpublished.')
      loadPapers()
    } catch {
      toast.error('Failed to unpublish paper.')
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Editorial Papers Workbench</h1>
          <p className="text-sm text-muted-foreground">
            Manage official exam sittings, import question skeletons, and publish verified allocations.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button onClick={() => setIsCreateOpen(true)} size="sm">
            Create Paper
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="h-48 animate-pulse rounded-xl bg-muted/40" />
      ) : (
        <PaperProgressBoard papers={papers} onPublish={handlePublish} onUnpublish={handleUnpublish} />
      )}

      {/* Create Paper Modal */}
      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Past Paper Sitting</DialogTitle>
            <DialogDescription>Create an official sitting container to allocate marks and questions.</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2 text-xs">
            <div className="space-y-1">
              <label htmlFor="create-subject-id" className="font-medium text-foreground">
                Subject UUID
              </label>
              <Input
                id="create-subject-id"
                value={subjectId}
                onChange={(e) => setSubjectId(e.target.value)}
                placeholder="00000000-0000-0000-0000-000000000000"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="create-term-code" className="font-medium text-foreground">
                Term Code (e.g. 2026-05)
              </label>
              <Input id="create-term-code" value={termCode} onChange={(e) => setTermCode(e.target.value)} />
            </div>

            <div className="space-y-1">
              <label htmlFor="create-paper-kind" className="font-medium text-foreground">
                Paper Kind (e.g. exam, mtp, rtp)
              </label>
              <Input id="create-paper-kind" value={paperKind} onChange={(e) => setPaperKind(e.target.value)} />
            </div>

            <div className="space-y-1">
              <label htmlFor="create-total-marks" className="font-medium text-foreground">
                Total Marks
              </label>
              <Input
                id="create-total-marks"
                type="number"
                value={totalMarks}
                onChange={(e) => setTotalMarks(parseFloat(e.target.value) || 100)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreatePaper} disabled={isCreating}>
              {isCreating ? 'Creating...' : 'Create Paper'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
