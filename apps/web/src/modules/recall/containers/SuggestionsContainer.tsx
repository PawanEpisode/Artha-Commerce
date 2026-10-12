import { Alert, Button, ButtonLink, EmptyState, Skeleton, Sparkles, toast } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'

import { AiConsentPanel } from '../components/AiConsentPanel'
import { ChapterPicker, type PickedChapter } from '../components/ChapterPicker'
import { LoadError, RecallShell } from '../components/RecallShell'
import { SuggestionTray } from '../components/SuggestionTray'
import { SuggestRequestForm } from '../components/SuggestRequestForm'
import { useOnlineStatus } from '../hooks/useRecallBasics'
import {
  useAcceptSuggestion,
  useAiConsent,
  useAiOverview,
  useGrantAiConsent,
  useRecallAiEnabled,
  useRejectSuggestion,
  useRequestSuggestions,
  useSuggestionBatch,
  useWithdrawAiConsent,
} from '../hooks/useSuggestions'
import type { AiOverview, AiSource, Suggestion } from '../lib/schemas'
import { requestProblem, suggestionFailure } from '../lib/suggestions'
import type { SuggestionsSearch } from '../lib/suggestionSearch'

function Header() {
  return (
    <header className="space-y-1">
      <h1 className="text-3xl font-extrabold">Suggest cards with AI</h1>
      <p className="text-muted-foreground">
        The AI drafts cards from your own material. Every card shows the words it came from, and nothing is added until
        you say so.
      </p>
    </header>
  )
}

function Unavailable({ text }: { text: string }) {
  return (
    <EmptyState
      icon={<Sparkles aria-hidden />}
      title="AI suggestions are not available"
      description={text}
      action={
        <ButtonLink asChild>
          <Link to="/app/recall/cards/new">Make a card yourself</Link>
        </ButtonLink>
      }
    />
  )
}

function Working({ overview, search }: { overview: AiOverview; search: SuggestionsSearch }) {
  const online = useOnlineStatus()
  const ask = useRequestSuggestions()
  const withdraw = useWithdrawAiConsent()
  const [chapter, setChapter] = useState<PickedChapter | null>(null)
  const [sources, setSources] = useState<AiSource[]>(overview.sources.includes('notes') ? ['notes'] : [])
  const [pasted, setPasted] = useState('')
  const [count, setCount] = useState(overview.limits.default_count)
  const [batchId, setBatchId] = useState<string | undefined>(search.batch)
  const [rowError, setRowError] = useState<{ id: string; text: string } | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const chapterId = chapter?.id ?? search.chapter ?? null
  const batch = useSuggestionBatch(batchId)
  const accept = useAcceptSuggestion(batchId ?? '')
  const reject = useRejectSuggestion(batchId ?? '')
  const problem = requestProblem({ chapterId, sources, pasted, count }, overview)

  const change =
    <T,>(set: (v: T) => void) =>
    (v: T) => {
      set(v)
      ask.fresh() // a different request must not join the old batch
      ask.reset()
    }

  const submit = () => {
    if (!chapterId) return
    ask.mutate(
      {
        chapter_id: chapterId,
        sources,
        count,
        ...(sources.includes('pasted') ? { pasted_text: pasted } : {}),
      },
      { onSuccess: (b) => setBatchId(b.id) },
    )
  }

  const decide = (s: Suggestion, run: () => Promise<unknown>) => {
    setRowError(null)
    setBusyId(s.id)
    run()
      .catch((e: unknown) => setRowError({ id: s.id, text: suggestionFailure(e) }))
      .finally(() => setBusyId(null))
  }

  return (
    <>
      <SuggestRequestForm
        overview={overview}
        chapterField={<ChapterPicker onPick={change(setChapter)} />}
        sources={sources}
        onSources={change(setSources)}
        pasted={pasted}
        onPasted={change(setPasted)}
        count={count}
        onCount={change(setCount)}
        problem={problem}
        pending={ask.isPending}
        offline={!online}
        error={ask.isError ? suggestionFailure(ask.error) : null}
        onSubmit={submit}
      />

      {batchId ? (
        batch.isPending ? (
          <Skeleton className="h-28 w-full" />
        ) : batch.isError || !batch.data ? (
          <LoadError what="these suggestions" onRetry={() => void batch.refetch()} />
        ) : (
          <SuggestionTray
            batch={batch.data}
            busyId={busyId}
            error={rowError}
            onAccept={(s, fields) =>
              decide(s, () =>
                accept.mutateAsync({ id: s.id, fields }).then(() => toast.success('Added to your cards.')),
              )
            }
            onReject={(s) => decide(s, () => reject.mutateAsync(s.id))}
          />
        )
      ) : null}

      <footer className="border-t border-border pt-4">
        <Button
          variant="outline"
          disabled={withdraw.isPending}
          onClick={() =>
            withdraw.mutate(undefined, {
              onSuccess: () => {
                setBatchId(undefined)
                toast.success('Your agreement is withdrawn and waiting suggestions are deleted.')
              },
            })
          }
        >
          Withdraw my agreement
        </Button>
        <p className="mt-2 text-sm text-muted-foreground">
          This deletes suggestions you have not decided on. Cards you already added stay.
        </p>
        {withdraw.isError ? <Alert variant="error">{suggestionFailure(withdraw.error)}</Alert> : null}
      </footer>
    </>
  )
}

function Body({ search }: { search: SuggestionsSearch }) {
  const overview = useAiOverview()
  const consentOn = overview.data ? !overview.data.consent.given : false
  const consent = useAiConsent(consentOn)
  const grant = useGrantAiConsent()

  if (overview.isPending) return <Skeleton className="h-48 w-full" />
  if (overview.isError || !overview.data) return <LoadError what="this page" onRetry={() => void overview.refetch()} />
  if (!overview.data.available)
    return <Unavailable text="This is paused for now. You can still make cards yourself, or import them." />
  if (!overview.data.consent.given) {
    if (consent.isPending) return <Skeleton className="h-48 w-full" />
    if (consent.isError || !consent.data) return <LoadError what="the notice" onRetry={() => void consent.refetch()} />
    return (
      <AiConsentPanel
        consent={consent.data}
        pending={grant.isPending}
        error={grant.isError ? suggestionFailure(grant.error) : null}
        onAgree={() => grant.mutate(consent.data.version)}
      />
    )
  }
  return <Working overview={overview.data} search={search} />
}

export function SuggestionsContainer({ search }: { search: SuggestionsSearch }) {
  const enabled = useRecallAiEnabled()
  return (
    <RecallShell>
      <Header />
      {enabled ? (
        <Body search={search} />
      ) : (
        <Unavailable text="We are rolling this out gradually. Please check back soon." />
      )}
    </RecallShell>
  )
}
