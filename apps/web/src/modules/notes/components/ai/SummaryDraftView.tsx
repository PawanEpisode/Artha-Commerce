import { Alert, Badge, Button, Card, Check, LoaderCircle, Pencil, Trash2 } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { RichText } from '~/lib/richtext'

import { AI_LABEL, dropNote, failureText, progressText, sourceLabel, withoutSourcesSection } from '../../lib/ai-copy'
import { isSummaryActive, type SummaryJob, type SummarySource } from '../../lib/ai-types'

interface SummaryDraftViewProps {
  job: SummaryJob
  busy: boolean
  failed: boolean
  onAccept: () => void
  onEdit: () => void
  onDiscard: () => void
  onCancel: () => void
}

function SourceLink({ source }: { source: SummarySource }) {
  const label = sourceLabel(source)
  if (source.kind === 'highlight' && source.document_id) {
    return (
      <Link
        to="/app/notes/pdf/$docId"
        params={{ docId: source.document_id }}
        search={source.page ? { page: source.page } : {}}
        className="underline underline-offset-4"
      >
        {label}
      </Link>
    )
  }
  if (source.kind === 'note') {
    return (
      <Link to="/app/notes/n/$noteId" params={{ noteId: source.id }} className="underline underline-offset-4">
        {label}
      </Link>
    )
  }
  return <span>{label}</span>
}

/** The summary job in whatever state it is in: waiting, a draft to check, saved, or stopped with a plain reason. */
export function SummaryDraftView({ job, busy, failed, onAccept, onEdit, onDiscard, onCancel }: SummaryDraftViewProps) {
  if (isSummaryActive(job.status)) {
    return (
      <Card className="max-w-3xl space-y-3 p-4" role="status" aria-live="polite">
        <p className="flex items-center gap-2">
          <LoaderCircle aria-hidden className="size-5 animate-spin" /> {progressText(job)}
        </p>
        <Button variant="outline" size="sm" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </Card>
    )
  }
  if (job.status === 'accepted' && job.result_note_id) {
    return (
      <Alert variant="success">
        <span className="flex flex-wrap items-center gap-3">
          <span>Saved to your notes.</span>
          <Button size="sm" variant="outline" asChild>
            <Link to="/app/notes/n/$noteId" params={{ noteId: job.result_note_id }}>
              Open the note
            </Link>
          </Button>
        </span>
      </Alert>
    )
  }
  if (job.status !== 'ready' || !job.draft) {
    const message =
      job.status === 'expired'
        ? 'This draft was not saved in time and has been removed.'
        : job.status === 'discarded' || job.status === 'cancelled'
          ? 'This summary was stopped. Nothing was kept.'
          : job.status === 'budget_blocked'
            ? 'AI help is busy for today. Please try again tomorrow. Nothing was used from your allowance.'
            : failureText(job.error_code)
    return <Alert variant={job.status === 'failed' ? 'error' : 'info'}>{message}</Alert>
  }
  const { draft } = job
  const dropped = dropNote(draft.dropped)
  return (
    <div className="grid items-start gap-x-6 gap-y-4 lg:grid-cols-[minmax(0,48rem)_20rem]">
      <Card className="min-w-0 space-y-3 p-4">
        <h2 className="text-base font-semibold break-words">{draft.title}</h2>
        <RichText markdown={withoutSourcesSection(draft.body_md)} />
      </Card>
      <aside
        aria-label="Summary details"
        className="min-w-0 space-y-3 lg:sticky lg:top-[calc(var(--site-header-height,2.75rem)+1rem)]"
      >
        <Badge variant="outline">{AI_LABEL}</Badge>
        {failed ? <Alert variant="error">That did not work. Please try again.</Alert> : null}
        <div className="flex flex-wrap gap-2">
          <Button onClick={onAccept} disabled={busy}>
            <Check aria-hidden /> Save to my notes
          </Button>
          <Button variant="outline" onClick={onEdit} disabled={busy}>
            <Pencil aria-hidden /> Edit first
          </Button>
          <Button variant="outline" onClick={onDiscard} disabled={busy}>
            <Trash2 aria-hidden /> Discard
          </Button>
        </div>
        {dropped ? <p className="text-xs text-muted-foreground">{dropped}</p> : null}
        {draft.sources.length > 0 ? (
          <section aria-labelledby="summary-sources" className="space-y-1.5 rounded-lg border bg-card p-3">
            <h3 id="summary-sources" className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Where each point came from
            </h3>
            <ol className="space-y-1 text-[13px]">
              {draft.sources.map((source) => (
                <li key={`${source.kind}-${source.id}`}>
                  <span className="text-muted-foreground">[{source.n}]</span> <SourceLink source={source} />
                </li>
              ))}
            </ol>
          </section>
        ) : null}
      </aside>
    </div>
  )
}
