import { Badge, Button, toast } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import * as React from 'react'

import * as api from '../api'
import { AllocationEditor } from '../components/AllocationEditor'
import type { EditorialPaperDetail } from '../types'

export interface WorkbenchContainerProps {
  paperId: string
}

export function WorkbenchContainer({ paperId }: WorkbenchContainerProps) {
  const [paper, setPaper] = React.useState<EditorialPaperDetail | null>(null)
  const [selectedQuestionId, setSelectedQuestionId] = React.useState<string | null>(null)
  const [isLoading, setIsLoading] = React.useState(true)
  const [isSaving, setIsSaving] = React.useState(false)

  const loadDetail = React.useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await api.fetchEditorialPaperDetail(paperId)
      setPaper(data)
      if (data.questions.length > 0 && !selectedQuestionId) {
        setSelectedQuestionId(data.questions[0].id)
      }
    } catch {
      toast.error('Failed to load paper details.')
    } finally {
      setIsLoading(false)
    }
  }, [paperId, selectedQuestionId])

  React.useEffect(() => {
    loadDetail()
  }, [loadDetail])

  const selectedQuestion = paper?.questions.find((q) => q.id === selectedQuestionId)

  const handleSaveAllocations = async (allocations: { chapter_id: string; marks: number }[]) => {
    if (!selectedQuestion) return
    setIsSaving(true)
    try {
      await api.setQuestionAllocations(selectedQuestion.id, allocations, selectedQuestion.rev)
      toast.success('Allocations saved.')
      await loadDetail()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Failed to save allocations.')
    } finally {
      setIsSaving(false)
    }
  }

  const handleConfirmQuestion = async () => {
    if (!selectedQuestion) return
    setIsSaving(true)
    try {
      await api.confirmQuestion(selectedQuestion.id, selectedQuestion.rev)
      toast.success('Question allocations confirmed!')
      await loadDetail()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Failed to confirm question.')
    } finally {
      setIsSaving(false)
    }
  }

  const handlePublish = async () => {
    if (!paper) return
    try {
      await api.publishPaper(paper.id)
      toast.success('Paper successfully published!')
      loadDetail()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Failed to publish.')
    }
  }

  if (isLoading || !paper) {
    return (
      <div className="mx-auto max-w-6xl space-y-4 p-6">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="h-64 animate-pulse rounded-xl bg-muted/40" />
      </div>
    )
  }

  const confirmedMarksNum = parseFloat(paper.confirmed_marks)
  const totalMarksNum = parseFloat(paper.total_marks)
  const isPublishReady = confirmedMarksNum >= totalMarksNum * 0.95

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Link to="/app/admin/analysis/papers" className="hover:underline">
              Editorial Papers
            </Link>
            <span>/</span>
            <span className="font-mono">{paper.term_code}</span>
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-foreground">{paper.title}</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Confirmed: <strong className="font-mono text-foreground">{paper.confirmed_marks}</strong> /{' '}
            {paper.total_marks}m ({paper.question_count} questions)
          </p>
        </div>

        <div className="flex items-center gap-2">
          {paper.status !== 'published' ? (
            <Button onClick={handlePublish} disabled={!isPublishReady} size="sm">
              Publish Paper (95% Rule)
            </Button>
          ) : (
            <Badge variant="default">Published</Badge>
          )}
        </div>
      </div>

      {/* Two Pane Layout */}
      <div className="grid grid-cols-1 items-start gap-6 md:grid-cols-12">
        {/* Left: Questions List */}
        <div className="overflow-hidden rounded-xl border border-border bg-card shadow-xs md:col-span-5">
          <div className="border-b border-border bg-muted/40 p-3 text-xs font-semibold text-foreground">
            Questions ({paper.questions.length})
          </div>

          <div className="max-h-[600px] divide-y divide-border/60 overflow-y-auto">
            {paper.questions.map((q) => {
              const isSelected = q.id === selectedQuestionId
              const isConfirmed = q.alloc_state === 'confirmed'

              return (
                <button
                  type="button"
                  key={q.id}
                  onClick={() => setSelectedQuestionId(q.id)}
                  className={`flex w-full items-center justify-between p-3 text-left text-xs transition-colors ${
                    isSelected ? 'bg-primary/10 font-semibold' : 'hover:bg-muted/30'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-medium text-foreground">{q.label}</span>
                    <span className="text-muted-foreground">({q.marks}m)</span>
                    <span className="text-[10px] text-muted-foreground uppercase">{q.format}</span>
                  </div>

                  <Badge variant={isConfirmed ? 'default' : 'outline'} className="h-4 px-1.5 py-0 text-[10px]">
                    {q.alloc_state}
                  </Badge>
                </button>
              )
            })}
          </div>
        </div>

        {/* Right: Allocation Editor */}
        <div className="md:col-span-7">
          {selectedQuestion ? (
            <AllocationEditor
              question={selectedQuestion}
              onSaveAllocations={handleSaveAllocations}
              onConfirmQuestion={handleConfirmQuestion}
              isSaving={isSaving}
            />
          ) : (
            <div className="rounded-xl border border-dashed p-12 text-center text-sm text-muted-foreground">
              Select a question to edit chapter allocations.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
