import { Alert, Button, ButtonLink, Card, PageHeader, SelectField, toast } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useMemo, useRef, useState } from 'react'

import { CardFields, CardPreview, type Importance, ImportanceField, TagsField } from '../components/CardEditor'
import { ChapterPicker, type PickedChapter } from '../components/ChapterPicker'
import { NewCardModes } from '../components/NewCardModes'
import { RecallShell } from '../components/RecallShell'
import { useCardQueue, useCreateCard } from '../hooks/useCardScreens'
import { useOnlineStatus } from '../hooks/useRecallBasics'
import type { CreateCardBody } from '../lib/api'
import { cardFailure } from '../lib/cardErrors'
import { KIND_LABELS } from '../lib/cardKinds'
import {
  CARD_KINDS,
  type CardKind,
  emptyFields,
  type FieldIssue,
  type Fields,
  parseTags,
  suggestKind,
  validateForm,
  validateTags,
  withDraft,
} from '../lib/cardKinds'
import type { NewCardSearch } from '../lib/cardSearch'
import { errorText } from '../lib/errors'
import { ImportContainer } from './ImportContainer'
import { SuggestLink } from './SuggestLink'

type Saved = { count: number; firstId: string | null; queued: boolean }

const newId = (): string => crypto.randomUUID()

function NewCardHeader() {
  return <PageHeader title="Make a card" description="One idea per card works best." />
}

function NewCard({ search }: { search: NewCardSearch }) {
  const online = useOnlineStatus()
  const create = useCreateCard()
  const offline = useCardQueue()
  const draft = search.draft?.trim() || ''
  const initialKind: CardKind = search.kind ?? (draft ? suggestKind(draft) : 'pointer')

  const [kind, setKind] = useState<CardKind>(initialKind)
  const [fields, setFields] = useState<Fields>(draft ? withDraft(initialKind, draft) : emptyFields(initialKind))
  const [importance, setImportance] = useState<Importance>('bullet')
  const [tags, setTags] = useState('')
  const [chapter, setChapter] = useState<PickedChapter | null>(null)
  const [attempted, setAttempted] = useState(false)
  const [serverIssues, setServerIssues] = useState<FieldIssue[]>([])
  const [duplicate, setDuplicate] = useState<{ cardId: string | null } | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [saved, setSaved] = useState<Saved | null>(null)
  // One id per card the student is making: a retry after a dropped answer can never make a second one.
  const clientId = useRef(newId())

  const tagList = useMemo(() => parseTags(tags), [tags])
  const tagError = validateTags(tagList)
  const local = useMemo(() => validateForm(kind, fields), [kind, fields])
  const issues = attempted ? [...local, ...serverIssues.filter((s) => !local.some((l) => l.field === s.field))] : []

  const changeKind = (next: CardKind) => {
    setKind(next)
    setFields((prev) => ({
      ...emptyFields(next),
      ...Object.fromEntries(Object.entries(prev).filter(([k]) => k in emptyFields(next))),
    }))
    setServerIssues([])
    setDuplicate(null)
  }

  const reset = () => {
    setFields(emptyFields(kind))
    setTags('')
    setAttempted(false)
    setServerIssues([])
    setDuplicate(null)
    setProblem(null)
    setSaved(null)
    clientId.current = newId()
  }

  const body = (force: boolean): CreateCardBody => ({
    client_id: clientId.current,
    kind,
    fields,
    importance,
    tags: tagList,
    chapter_id: chapter?.id ?? search.chapter ?? null,
    topic_id: search.topic ?? null,
    deck_ids: search.deck ? [search.deck] : [],
    force,
  })

  const queueIt = (b: CreateCardBody) => {
    const outcome = offline.queue(b)
    if (outcome === 'queued') setSaved({ count: 1, firstId: null, queued: true })
    else if (outcome === 'full')
      setProblem('Too many cards are waiting on this device. Connect to the internet so they can be added.')
    else setProblem('This device could not keep the card. Copy your text and try again when you are online.')
  }

  const submit = (force = false) => {
    setAttempted(true)
    setProblem(null)
    setDuplicate(null)
    if (local.length > 0 || tagError) return
    const b = body(force)
    if (!online) return queueIt(b)
    create.mutate(b, {
      onSuccess: (r) => {
        setSaved({ count: r.cards.length, firstId: r.cards[0]?.id ?? null, queued: false })
        if (r.existing) toast.info('You already had this card.')
      },
      onError: (error) => {
        const f = cardFailure(error)
        if (f.kind === 'network') return queueIt(b)
        if (f.kind === 'duplicate') return setDuplicate({ cardId: f.cardId })
        if (f.kind === 'invalid') return setServerIssues(f.issues)
        if (f.kind === 'quota') return setProblem(f.message)
        if (f.kind === 'throttled') return setProblem('Too many cards at once. Wait a moment and try again.')
        setProblem(errorText(error, 'We could not save this card. Please try again.'))
      },
    })
  }

  if (saved) {
    return (
      <section
        aria-labelledby="saved-heading"
        className="max-w-xl space-y-3 rounded-lg border border-border bg-card p-4"
        role="status"
      >
        <h1 id="saved-heading" className="text-lg font-semibold">
          {saved.queued ? 'Saved on this device' : saved.count > 1 ? `${saved.count} cards made` : 'Card made'}
        </h1>
        <p className="text-[13px] text-muted-foreground">
          {saved.queued
            ? 'It will be added to your cards as soon as you are back online.'
            : 'It will show up in your reviews soon.'}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button onClick={reset}>Make another</Button>
          {saved.firstId ? (
            <ButtonLink variant="outline" asChild>
              <Link to="/app/recall/cards/$cardId" params={{ cardId: saved.firstId }}>
                Open the card
              </Link>
            </ButtonLink>
          ) : null}
          <ButtonLink variant="ghost" asChild>
            <Link to="/app/recall/cards" search={{}}>
              See your cards
            </Link>
          </ButtonLink>
        </div>
      </section>
    )
  }

  return (
    <>
      <NewCardHeader />
      <NewCardModes search={search} extra={<SuggestLink chapter={search.chapter} />} />

      {search.from === 'selection' ? (
        <Alert variant="info">Made from the text you selected. Change it however you like.</Alert>
      ) : null}
      {!online ? (
        <Alert variant="info">You are offline. The card will be kept on this device and added later.</Alert>
      ) : null}
      {offline.pending > 0 ? (
        <Alert variant="info">
          {offline.pending === 1 ? '1 card is' : `${offline.pending} cards are`} waiting on this device to be added.
        </Alert>
      ) : null}

      <form
        className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start"
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          submit(false)
        }}
      >
        <Card className="min-w-0 space-y-4 p-4">
          <div className="grid gap-1.5">
            <label htmlFor="card-kind" className="text-[13px] font-medium">
              Kind of card
            </label>
            <SelectField
              id="card-kind"
              className="sm:max-w-xs"
              value={kind}
              onValueChange={(v) => changeKind(v as CardKind)}
              options={CARD_KINDS.map((k) => ({ value: k, label: KIND_LABELS[k].label }))}
            />
            <p className="text-xs text-muted-foreground">{KIND_LABELS[kind].blurb}</p>
          </div>

          <CardFields
            kind={kind}
            fields={fields}
            onField={(name, value) => {
              setFields((f) => ({ ...f, [name]: value }))
              setServerIssues((s) => s.filter((i) => i.field !== name))
              setDuplicate(null)
            }}
            issues={issues}
          />
        </Card>

        <div className="min-w-0 space-y-3">
          <Card className="space-y-3 p-4">
            <ImportanceField value={importance} onChange={setImportance} />
            <TagsField value={tags} onChange={setTags} error={attempted ? tagError : null} />
            <div className="space-y-1.5">
              <ChapterPicker stacked label="Chapter (optional)" onPick={setChapter} />
              {!chapter && search.chapter ? (
                <p className="text-xs text-muted-foreground">
                  It will go in the chapter you came from unless you pick another.
                </p>
              ) : null}
            </div>
          </Card>

          <CardPreview kind={kind} fields={fields} />

          {duplicate ? (
            <Alert variant="info">
              <span className="flex flex-wrap items-center gap-2">
                You already have a card with this text.
                {duplicate.cardId ? (
                  <ButtonLink variant="outline" size="sm" asChild>
                    <Link to="/app/recall/cards/$cardId" params={{ cardId: duplicate.cardId }}>
                      Open it
                    </Link>
                  </ButtonLink>
                ) : null}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={create.isPending}
                  onClick={() => submit(true)}
                >
                  Keep both
                </Button>
              </span>
            </Alert>
          ) : null}
          {problem ? <Alert variant="error">{problem}</Alert> : null}
          {attempted && (local.length > 0 || tagError) ? (
            <Alert variant="error" role="alert">
              {local.length + (tagError ? 1 : 0) === 1 ? 'One thing needs fixing.' : 'A few things need fixing.'} It is
              marked in the form.
            </Alert>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? 'Saving…' : 'Save card'}
            </Button>
            <ButtonLink variant="ghost" asChild>
              <Link to="/app/recall/cards" search={{}}>
                Cancel
              </Link>
            </ButtonLink>
          </div>
        </div>
      </form>
    </>
  )
}

export function NewCardContainer({ search }: { search: NewCardSearch }) {
  return (
    <RecallShell>
      {search.mode === 'import' ? (
        <>
          <NewCardHeader />
          <ImportContainer search={search} />
        </>
      ) : (
        <NewCard search={search} />
      )}
    </RecallShell>
  )
}
