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
      <Card className="space-y-4 p-6" role="status" aria-live="polite">
        <p className="flex items-center gap-2">
          <LoaderCircle aria-hidden className="size-5 animate-spin" /> {progressText(job)}
        </p>
        <Button variant="outline" onClick={onCancel} disabled={busy}>
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
    <div className="space-y-4">
      <Badge variant="outline">{AI_LABEL}</Badge>
      <Card className="space-y-3 p-6">
        <h2 className="font-display text-2xl font-bold break-words">{draft.title}</h2>
        <RichText markdown={withoutSourcesSection(draft.body_md)} />
      </Card>
      {dropped ? <p className="text-sm text-muted-foreground">{dropped}</p> : null}
      {draft.sources.length > 0 ? (
        <section aria-labelledby="summary-sources" className="space-y-2">
          <h3 id="summary-sources" className="font-semibold">
            Where each point came from
          </h3>
          <ol className="space-y-1 text-sm">
            {draft.sources.map((source) => (
              <li key={`${source.kind}-${source.id}`}>
                <span className="text-muted-foreground">[{source.n}]</span> <SourceLink source={source} />
              </li>
            ))}
          </ol>
        </section>
      ) : null}
      {failed ? <Alert variant="error">That did not work. Please try again.</Alert> : null}
      <div className="flex flex-wrap gap-3">
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
    </div>
  )
}
