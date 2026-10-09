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
import { ChapterPicker, type PickedChapter } from '../components/ChapterPicker'
import { ConflictDialog } from '../components/ConflictDialog'
import { LoadError, RecallShell } from '../components/RecallShell'
import {
  useBulkCards,
  useCard,
  useCardHistory,
  useCardQueue,
  useCardState,
  useDeleteCard,
  usePatchCard,
  useUndoDelete,
} from '../hooks/useCardScreens'
import { useOnlineStatus, useRecallUser } from '../hooks/useRecallBasics'
import { recallApi } from '../lib/api'
import { type Merge, mergeFields } from '../lib/cardConflict'
import { cardEditQueue, type QueuedEdit } from '../lib/cardEditQueue'
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
  const userId = useRecallUser()
  const patch = usePatchCard(card.id)
  const offline = useCardQueue()
  // An edit written offline (or one the server sent back) is picked up where she left it.
  const [queued] = useState<QueuedEdit | null>(() => (userId ? cardEditQueue.get(userId, card.id) : null))
  const [base, setBase] = useState<Base>(() => {
    const b = baseOf(card, kind)
    return queued ? { ...b, rev: queued.baseRev, fields: queued.base } : b
  })
  const [fields, setFields] = useState<Fields>(queued ? queued.fields : base.fields)
  const [importance, setImportance] = useState<Importance>(queued ? queued.importance : base.importance)
  const [tags, setTags] = useState(queued ? queued.tags.join(', ') : base.tags)
  const [attempted, setAttempted] = useState(false)
  const [serverIssues, setServerIssues] = useState<FieldIssue[]>([])
  const [problem, setProblem] = useState<string | null>(null)
  const [keptOffline, setKeptOffline] = useState(queued !== null && queued.attention === null)
  const [merge, setMerge] = useState<{ merge: Merge; rev: number } | null>(() =>
    queued?.attention?.kind === 'conflict'
      ? { merge: mergeFields(queued.base, queued.fields, queued.attention.theirs), rev: queued.attention.rev }
      : null,
  )
  const [lost, setLost] = useState(queued?.attention?.kind === 'deleted')

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

  /** No connection: the edit waits on this device with the version she started from, and is sent when it is back. */
  const queueIt = (nextFields: Fields) => {
    const outcome = offline.queueEdit({
      cardId: card.id,
      kind,
      baseRev: base.rev,
      base: base.fields,
      fields: nextFields,
      importance,
      tags: tagList,
    })
    setMerge(null)
    if (outcome === 'queued') setKeptOffline(true)
    else if (outcome === 'full')
      setProblem('Too many edits are waiting on this device. Connect to the internet so they can be sent.')
    else setProblem('This device could not keep your edit. Copy your text and try again when you are online.')
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
          offline.dropEdit(card.id)
          setKeptOffline(false)
          setLost(false)
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
          if (f.kind === 'network') return queueIt(nextFields)
          setProblem(errorText(error, 'We could not save your changes. Please try again.'))
        },
      },
    )

  const save = () => {
    setAttempted(true)
    setProblem(null)
    if (local.length > 0 || tagError) return
    if (!online) return queueIt(fields)
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
      {lost ? (
        <Alert variant="info">
          <span className="flex flex-wrap items-center gap-3">
            This card was deleted somewhere else. Your edit is kept here so you can copy it.
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                offline.dropEdit(card.id)
                setLost(false)
              }}
            >
              Discard my edit
            </Button>
          </span>
        </Alert>
      ) : null}
      {queued?.attention?.kind === 'invalid' ? (
        <Alert variant="error">Your offline edit could not be saved: {queued.attention.message}</Alert>
      ) : null}
      {keptOffline ? (
        <Alert variant="info">
          {online
            ? 'Your edit is waiting to be sent.'
            : 'Saved on this device. It will be sent when you are back online.'}
        </Alert>
      ) : !online ? (
        <Alert variant="info">You are offline. You can keep editing; the change is sent when you are back.</Alert>
      ) : null}
      {problem ? <Alert variant="error">{problem}</Alert> : null}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" size="lg" disabled={!dirty || patch.isPending}>
          {patch.isPending ? 'Saving…' : online ? 'Save changes' : 'Save on this device'}
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

function ChapterMove({ card }: { card: RecallCardDetail }) {
  const online = useOnlineStatus()
  const bulk = useBulkCards()
  const [open, setOpen] = useState(false)
  const [picked, setPicked] = useState<PickedChapter | null>(null)

  const move = () => {
    if (!picked) return
    bulk.mutate(
      { ids: [card.id], action: 'move_chapter', args: { chapter_id: picked.id } },
      {
        onSuccess: () => {
          setOpen(false)
          setPicked(null)
          toast.success(`Moved to ${picked.name}`)
        },
        onError: (e) => toast.error(errorText(e, 'We could not move this card. Nothing was changed.')),
      },
    )
  }

  return (
    <section aria-labelledby="chapter-heading" className="space-y-3">
      <h2 id="chapter-heading" className="font-display text-xl font-bold">
        Chapter
      </h2>
      <p className="text-muted-foreground">
        {card.chapter?.name ? `This card belongs to ${card.chapter.name}.` : 'This card is not in a chapter.'}
      </p>
      {!open ? (
        <Button variant="outline" disabled={!online} onClick={() => setOpen(true)}>
          Move to another chapter
        </Button>
      ) : (
        <div className="space-y-3">
          <ChapterPicker label="Move to" onPick={setPicked} />
          <div className="flex gap-3">
            <Button disabled={!picked || bulk.isPending} onClick={move}>
              {bulk.isPending ? 'Moving…' : 'Move card'}
            </Button>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
      {!online ? <p className="text-sm text-muted-foreground">Moving a card needs the internet.</p> : null}
    </section>
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

      <ChapterMove card={card} />

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
