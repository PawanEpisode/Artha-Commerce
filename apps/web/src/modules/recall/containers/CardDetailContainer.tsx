import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  Skeleton,
  toast,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useMemo, useState } from 'react'

import { ApiError } from '~/lib/api'

import { CardFields, CardPreview, type Importance, ImportanceField, TagsField } from '../components/CardEditor'
import { kindLabel } from '../components/CardFace'
import { CardMemoryPanel, ReviewHistory } from '../components/CardMemory'
import { ConflictDialog } from '../components/ConflictDialog'
import { LoadError, RecallShell } from '../components/RecallShell'
import {
  useCard,
  useCardHistory,
  useCardState,
  useDeleteCard,
  usePatchCard,
  useUndoDelete,
} from '../hooks/useCardScreens'
import { useOnlineStatus } from '../hooks/useRecallBasics'
import { recallApi } from '../lib/api'
import { type Merge, mergeFields } from '../lib/cardConflict'
import { cardFailure } from '../lib/cardErrors'
import {
  type CardKind,
  type FieldIssue,
  type Fields,
  fieldsOf,
  isCardKind,
  parseTags,
  validateForm,
  validateTags,
} from '../lib/cardKinds'
import { errorText } from '../lib/errors'
import type { RecallCardDetail } from '../lib/schemas'

interface Base {
  rev: number
  fields: Fields
  importance: Importance
  tags: string
}

const importanceOf = (v: string | number): Importance => (v === 'important' || v === 'mandatory' ? v : 'bullet')
const baseOf = (card: RecallCardDetail, kind: CardKind): Base => ({
  rev: card.rev,
  fields: fieldsOf(kind, card.fields),
  importance: importanceOf(card.importance),
  tags: card.tags.join(', '),
})

function Editor({ card, kind }: { card: RecallCardDetail; kind: CardKind }) {
  const online = useOnlineStatus()
  const patch = usePatchCard(card.id)
  const [base, setBase] = useState<Base>(() => baseOf(card, kind))
  const [fields, setFields] = useState<Fields>(base.fields)
  const [importance, setImportance] = useState<Importance>(base.importance)
  const [tags, setTags] = useState(base.tags)
  const [attempted, setAttempted] = useState(false)
  const [serverIssues, setServerIssues] = useState<FieldIssue[]>([])
  const [problem, setProblem] = useState<string | null>(null)
  const [merge, setMerge] = useState<{ merge: Merge; rev: number } | null>(null)

  const tagList = useMemo(() => parseTags(tags), [tags])
  const tagError = validateTags(tagList)
  const local = useMemo(() => validateForm(kind, fields), [kind, fields])
  const issues = attempted ? [...local, ...serverIssues.filter((s) => !local.some((l) => l.field === s.field))] : []
  const dirty =
    importance !== base.importance ||
    tagList.join(', ') !== parseTags(base.tags).join(', ') ||
    Object.keys(fields).some((k) => (fields[k] ?? '') !== (base.fields[k] ?? ''))

  const apply = (saved: RecallCardDetail, merged?: Fields) => {
    const next = baseOf(saved, kind)
    setBase(next)
    setFields(merged ?? next.fields)
    setImportance(next.importance)
    setTags(next.tags)
    setMerge(null)
    setAttempted(false)
    setServerIssues([])
    setProblem(null)
  }

  const send = (rev: number, nextFields: Fields) =>
    patch.mutate(
      {
        base_rev: rev,
        fields: nextFields,
        importance,
        tags: tagList,
      },
      {
        onSuccess: (saved) => {
          apply(saved)
          toast.success('Saved')
        },
        onError: async (error) => {
          const f = cardFailure(error)
          if (f.kind === 'conflict') {
            const theirs = f.serverFields
            const rev2 =
              f.rev ??
              (await recallApi
                .card(card.id)
                .then((c) => c.rev)
                .catch(() => null))
            if (rev2 === null) return setProblem('This card was changed somewhere else. Reload the page to see it.')
            const m = mergeFields(base.fields, nextFields, { ...nextFields, ...theirs })
            if (m.conflicts.length === 0) {
              // Only one side changed each part: nothing to ask. Send the merge on top of what the server has.
              toast.info('Merged changes made on another device.')
              return send(rev2, m.merged)
            }
            return setMerge({ merge: m, rev: rev2 })
          }
          if (f.kind === 'invalid') return setServerIssues(f.issues)
          if (f.kind === 'deleted') return setProblem('This card was deleted somewhere else.')
          if (f.kind === 'network')
            return setProblem('You seem to be offline. Your changes are still here; save again when you are connected.')
          setProblem(errorText(error, 'We could not save your changes. Please try again.'))
        },
      },
    )

  const save = () => {
    setAttempted(true)
    setProblem(null)
    if (local.length > 0 || tagError) return
    send(base.rev, fields)
  }

  const faces =
    kind === 'cloze' ? (card.fields.text_md ? (String(card.fields.text_md).match(/\{\{c\d+::/g)?.length ?? 1) : 1) : 1

  return (
    <form
      className="space-y-5"
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        save()
      }}
    >
      <h2 className="font-display text-xl font-bold">Edit</h2>
      {faces > 1 ? <Alert variant="info">This item makes {faces} cards. Changing it changes all of them.</Alert> : null}
      <CardFields
        kind={kind}
        fields={fields}
        onField={(n, v) => setFields((f) => ({ ...f, [n]: v }))}
        issues={issues}
      />
      <ImportanceField value={importance} onChange={setImportance} />
      <TagsField value={tags} onChange={setTags} error={attempted ? tagError : null} />
      <CardPreview kind={kind} fields={fields} />
      {!online ? <Alert variant="info">You are offline. Connect to save your changes.</Alert> : null}
      {problem ? <Alert variant="error">{problem}</Alert> : null}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" size="lg" disabled={!dirty || patch.isPending || !online}>
          {patch.isPending ? 'Saving…' : 'Save changes'}
        </Button>
        {dirty ? (
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setFields(base.fields)
              setImportance(base.importance)
              setTags(base.tags)
              setAttempted(false)
            }}
          >
            Discard changes
          </Button>
        ) : null}
      </div>
      {merge ? (
        <ConflictDialog
          merge={merge.merge}
          busy={patch.isPending}
          onCancel={() => setMerge(null)}
          onResolve={(resolved) => {
            setFields(resolved)
            send(merge.rev, resolved)
          }}
        />
      ) : null}
    </form>
  )
}

function Actions({ card }: { card: RecallCardDetail }) {
  const navigate = useNavigate()
  const state = useCardState(card.id)
  const del = useDeleteCard()
  const undo = useUndoDelete()
  const [confirm, setConfirm] = useState<'reset' | 'delete' | null>(null)
  const paused = card.status === 'suspended'
  const recheck = card.badges.includes('recheck')

  const run = (action: Parameters<typeof state.mutate>[0], done: string) =>
    state.mutate(action, {
      onSuccess: () => {
        setConfirm(null)
        toast.success(done)
      },
      onError: (e) => toast.error(errorText(e, 'That did not work. Please try again.')),
    })

  const remove = () =>
    del.mutate(card.id, {
      onSuccess: (r) => {
        setConfirm(null)
        toast.success('Card deleted', {
          duration: Math.max(5, r.undo_seconds) * 1000,
          action: {
            label: 'Undo',
            onClick: () =>
              undo.mutate(r.undo_token, {
                onSuccess: () => toast.success('Card is back'),
                onError: (e) => toast.error(errorText(e, 'It is too late to undo this.')),
              }),
          },
        })
        void navigate({ to: '/app/recall/cards', search: {} })
      },
      onError: (e) => toast.error(errorText(e, 'We could not delete this card.')),
    })

  return (
    <section aria-labelledby="actions-heading" className="space-y-3">
      <h2 id="actions-heading" className="font-display text-xl font-bold">
        Actions
      </h2>
      <div className="flex flex-wrap gap-3">
        {paused ? (
          <Button
            variant="outline"
            disabled={state.isPending}
            onClick={() => run('unsuspend', 'Card is back in your reviews')}
          >
            Bring back
          </Button>
        ) : (
          <>
            <Button variant="outline" disabled={state.isPending} onClick={() => run('bury', 'Hidden until tomorrow')}>
              Skip until tomorrow
            </Button>
            <Button variant="outline" disabled={state.isPending} onClick={() => run('suspend', 'Card paused')}>
              Pause
            </Button>
          </>
        )}
        {recheck ? (
          <Button
            variant="outline"
            disabled={state.isPending}
            onClick={() => run('recheck-ok', 'Thanks, marked as checked')}
          >
            This card is still right
          </Button>
        ) : null}
        <Button variant="outline" onClick={() => setConfirm('reset')}>
          Reset memory
        </Button>
        <Button variant="danger" onClick={() => setConfirm('delete')}>
          Delete
        </Button>
      </div>
      <Dialog open={confirm !== null} onOpenChange={(open) => (!open ? setConfirm(null) : undefined)}>
        <DialogContent>
          <DialogTitle>{confirm === 'reset' ? 'Reset your memory of this card?' : 'Delete this card?'}</DialogTitle>
          <DialogDescription>
            {confirm === 'reset'
              ? 'It becomes a new card again and you will learn it from the start. Your past reviews are kept.'
              : 'It stops appearing in your reviews. You can undo for a few seconds afterwards.'}
          </DialogDescription>
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setConfirm(null)}>
              Cancel
            </Button>
            {confirm === 'reset' ? (
              <Button disabled={state.isPending} onClick={() => run('reset', 'Memory reset')}>
                Reset
              </Button>
            ) : (
              <Button variant="danger" disabled={del.isPending} onClick={remove}>
                Delete
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </section>
  )
}

function Detail({ id }: { id: string }) {
  const q = useCard(id)
  const history = useCardHistory(id)

  if (q.isPending) {
    return (
      <div aria-busy="true" className="space-y-4">
        <span className="sr-only" role="status">
          Loading your card…
        </span>
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }
  if (q.isError || !q.data) {
    const gone = q.error instanceof ApiError && (q.error.status === 404 || q.error.status === 410)
    return gone ? (
      <Alert variant="info">
        <span className="flex flex-wrap items-center gap-3">
          {q.error instanceof ApiError && q.error.status === 410
            ? 'This card was deleted.'
            : 'We could not find this card.'}
          <ButtonLink variant="outline" asChild>
            <Link to="/app/recall/cards" search={{}}>
              Back to your cards
            </Link>
          </ButtonLink>
        </span>
      </Alert>
    ) : (
      <LoadError what="this card" onRetry={() => void q.refetch()} />
    )
  }

  const card = q.data
  if (!isCardKind(card.kind)) return <Alert variant="error">This kind of card cannot be edited here yet.</Alert>

  return (
    <>
      <header className="space-y-2">
        <ButtonLink variant="ghost" asChild>
          <Link to="/app/recall/cards" search={{}}>
            Back to your cards
          </Link>
        </ButtonLink>
        <h1 className="text-3xl font-extrabold">{kindLabel(card.kind)}</h1>
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          {card.chapter?.name ? <span>{card.chapter.name}</span> : null}
          {card.source ? <span>From your {card.source.module === 'notes' ? 'notes' : 'highlights'}</span> : null}
          {card.badges.map((b) => (
            <Badge key={b} variant="outline">
              {{ suspended: 'Paused', tricky: 'Tricky', recheck: 'Needs a look', buried: 'Back tomorrow' }[b] ?? b}
            </Badge>
          ))}
        </div>
      </header>

      <section aria-labelledby="memory-heading" className="space-y-3">
        <h2 id="memory-heading" className="font-display text-xl font-bold">
          Your memory of it
        </h2>
        {card.memory ? <CardMemoryPanel memory={card.memory} /> : null}
      </section>

      {/* Remounting on the card id only: a background refresh never throws away what she is typing. */}
      <Editor key={card.id} card={card} kind={card.kind} />

      <Actions card={card} />

      <section aria-labelledby="history-heading" className="space-y-3">
        <h2 id="history-heading" className="font-display text-xl font-bold">
          Review history
        </h2>
        {history.isPending ? (
          <Skeleton className="h-20 w-full" />
        ) : history.isError ? (
          <LoadError what="the history" onRetry={() => void history.refetch()} />
        ) : (
          <ReviewHistory rows={history.data.items} />
        )}
      </section>
    </>
  )
}

export function CardDetailContainer({ cardId }: { cardId: string }) {
  return (
    <RecallShell>
      <Detail id={cardId} />
    </RecallShell>
  )
}
