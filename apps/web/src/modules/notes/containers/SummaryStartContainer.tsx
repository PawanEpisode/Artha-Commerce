import { Alert, Button, LoaderCircle, Skeleton } from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'

import { ConsentPanel } from '../components/ai/ConsentPanel'
import { useAiAvailable, useAiConsent, useGrantConsent, useStartSummary } from '../hooks/useAi'
import { useUsage } from '../hooks/useNotesQueries'
import { allowanceText, startFailureText, summaryAllowance } from '../lib/ai-copy'
import type { AiFailure } from '../lib/ai-errors'
import { NotesShell } from './NotesShell'

function Start({ chapterId }: { chapterId: string }) {
  const navigate = useNavigate()
  const ai = useAiAvailable()
  const consent = useAiConsent(ai.flag)
  const usage = useUsage()
  const grant = useGrantConsent()
  const start = useStartSummary()
  const [failure, setFailure] = useState<AiFailure | null>(null)
  const [declined, setDeclined] = useState(false)
  const started = useRef(false)

  const consented = consent.data?.consented === true
  const ready = ai.available && consented && !declined

  useEffect(() => {
    if (!ready || started.current || !chapterId) return
    started.current = true
    start.mutate(chapterId, {
      onSuccess: (result) => {
        if (result.ok)
          void navigate({ to: '/app/notes/summary/$jobId', params: { jobId: result.job.id }, replace: true })
        else {
          if (result.failure.reason === 'not_consented') started.current = false
          setFailure(result.failure)
        }
      },
    })
  }, [ready, chapterId, start, navigate])

  if (!ai.flag || (!ai.loading && !ai.available)) return <Alert>AI help is not available yet.</Alert>
  if (ai.loading || consent.isPending) return <Skeleton className="h-48 w-full" />
  if (!chapterId) return <Alert variant="error">Choose a chapter first, from its notes page.</Alert>
  const allowance = allowanceText(summaryAllowance(usage.data))

  return (
    <>
      <header className="space-y-1">
        <h1 className="font-display text-3xl font-extrabold">Write an exam summary</h1>
        {allowance ? <p className="text-muted-foreground">{allowance}</p> : null}
      </header>
      {consent.data && !consented && !declined ? (
        <ConsentPanel
          text={consent.data.text}
          pending={grant.isPending}
          failed={grant.isError}
          onAgree={() => grant.mutate(consent.data.text.version)}
          onCancel={() => setDeclined(true)}
        />
      ) : null}
      {declined ? (
        <Alert>
          Nothing was sent. You can write a summary any time, after you have read and agreed to how AI help works.
        </Alert>
      ) : null}
      {failure ? (
        <Alert variant="error">
          <span className="flex flex-wrap items-center gap-3">
            <span>{startFailureText(failure)}</span>
            <Button size="sm" variant="outline" asChild>
              <Link to="/app/notes">Back to notes</Link>
            </Button>
          </span>
        </Alert>
      ) : null}
      {ready && !failure ? (
        <p role="status" className="flex items-center gap-2">
          <LoaderCircle aria-hidden className="size-5 animate-spin" /> Starting your summary…
        </p>
      ) : null}
    </>
  )
}

export function SummaryStartContainer({ chapterId }: { chapterId: string }) {
  return (
    <NotesShell width="max-w-3xl">
      <Start chapterId={chapterId} />
    </NotesShell>
  )
}
