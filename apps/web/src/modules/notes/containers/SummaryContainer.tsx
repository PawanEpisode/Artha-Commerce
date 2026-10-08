import { Alert, Button, Skeleton } from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'

import { SummaryDraftView } from '../components/ai/SummaryDraftView'
import { useAcceptSummary, useAiAvailable, useCancelSummary, useDiscardSummary, useSummary } from '../hooks/useAi'
import { isNotFound } from '../lib/errors'
import { NotesShell } from './NotesShell'

function Summary({ jobId }: { jobId: string }) {
  const navigate = useNavigate()
  const ai = useAiAvailable()
  const job = useSummary(jobId)
  const accept = useAcceptSummary()
  const discard = useDiscardSummary()
  const cancel = useCancelSummary()
  const busy = accept.isPending || discard.isPending || cancel.isPending

  if (!ai.flag) return <Alert>AI help is not available yet.</Alert>
  if (job.isPending) return <Skeleton className="h-48 w-full" />
  if (job.isError || !job.data) {
    return (
      <Alert variant="error">
        {isNotFound(job.error) ? 'We could not find this summary.' : 'We could not load this summary.'}
      </Alert>
    )
  }
  const back = (
    <Button variant="outline" size="sm" asChild>
      <Link to="/app/notes">Back to notes</Link>
    </Button>
  )
  return (
    <>
      <header className="space-y-1">
        <h1 className="font-display text-3xl font-extrabold">Exam summary</h1>
        {back}
      </header>
      <SummaryDraftView
        job={job.data}
        busy={busy}
        failed={accept.isError || discard.isError || cancel.isError}
        onAccept={() => accept.mutate({ id: jobId })}
        onEdit={() =>
          accept.mutate(
            { id: jobId },
            {
              onSuccess: (done) =>
                void navigate({ to: '/app/notes/n/$noteId', params: { noteId: done.note.id }, search: {} }),
            },
          )
        }
        onDiscard={() => discard.mutate(jobId)}
        onCancel={() => cancel.mutate(jobId)}
      />
    </>
  )
}

export function SummaryContainer({ jobId }: { jobId: string }) {
  return (
    <NotesShell width="max-w-3xl">
      <Summary jobId={jobId} />
    </NotesShell>
  )
}
