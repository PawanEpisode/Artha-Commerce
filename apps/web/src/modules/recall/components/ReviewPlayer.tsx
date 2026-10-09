import {
  ArrowLeft,
  Badge,
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  FlipCard,
  Kbd,
  Keyboard,
  ProgressCounter,
  RatingButtons,
  Undo2,
} from '@artha/design-system'
import { useEffect, useRef, useState } from 'react'

import type { ReviewSession } from '../hooks/useReviewSession'
import { useShortcuts } from '../hooks/useShortcuts'
import type { SyncState } from '../hooks/useSync'
import { useVisualViewportHeight } from '../hooks/useVisualViewport'
import { trackRecall } from '../lib/analytics'
import { CardFace } from './CardFace'
import { FirstTimeIntro } from './FirstTimeIntro'
import { ShortcutsDialog } from './ShortcutsDialog'
import { SyncStatus } from './SyncStatus'

export interface ReviewPlayerProps {
  session: ReviewSession
  sync: Pick<SyncState, 'pending' | 'syncing' | 'online' | 'last' | 'syncNow'>
  introDone: boolean
  onIntroDone: () => void
  onLeave: () => void
  /** Open the card editor. Left out until the cards screens exist; then the E key and the menu item are hidden. */
  onEdit?: (cardId: string) => void
}

/**
 * The review screen. Full height of the visible viewport (keyboard and address bar aware), the card above, the answer
 * buttons in a bar at the bottom where a thumb reaches. Every gesture has a button and every button a key.
 */
export function ReviewPlayer({ session, sync, introDone, onIntroDone, onLeave, onEdit }: ReviewPlayerProps) {
  const { card, flipped } = session
  const [help, setHelp] = useState(false)
  const [message, setMessage] = useState('')
  const vvh = useVisualViewportHeight()
  const edit = onEdit && card ? () => onEdit(card.id) : undefined
  const interactive = introDone && session.status === 'ready' && card !== null

  const doHold = async (action: 'bury' | 'suspend') => {
    const ok = await session.hold(action)
    setMessage(
      ok
        ? action === 'bury'
          ? 'Card buried until tomorrow.'
          : 'Card suspended. You can bring it back from your cards.'
        : 'Could not do that. Check your connection and try again.',
    )
  }
  const doUndo = async () => {
    const ok = await session.undo()
    setMessage(ok ? 'Last answer undone.' : 'That answer can no longer be undone.')
  }

  useShortcuts(
    {
      flip: interactive && !flipped ? session.flip : undefined,
      undo: interactive && session.canUndo ? () => void doUndo() : undefined,
      edit: interactive ? edit : undefined,
      suspend: interactive && !session.offline ? () => void doHold('suspend') : undefined,
      bury: interactive && !session.offline ? () => void doHold('bury') : undefined,
      help: () => setHelp(true),
    },
    interactive,
  )

  const shown = useRef<string | null>(null)
  useEffect(() => {
    if (!card || shown.current === card.id) return
    shown.current = card.id
    if (card.badges.includes('tricky')) trackRecall('recall_leech_shown', { lapses: card.memory.lapses })
  }, [card])

  // When the answered card leaves, keyboard focus would fall to the page: bring it to the next card's Show answer button
  const showRef = useRef<HTMLButtonElement>(null)
  const lastCard = useRef<string | null>(null)
  useEffect(() => {
    const id = card?.id ?? null
    const changed = lastCard.current !== null && id !== null && lastCard.current !== id
    lastCard.current = id
    if (changed && !flipped && (document.activeElement === document.body || document.activeElement === null)) {
      showRef.current?.focus()
    }
  }, [card?.id, flipped])

  const tricky = card?.badges.includes('tricky') === true

  return (
    <div
      data-slot="review-player"
      className="mx-auto flex w-full max-w-2xl flex-col"
      style={{ height: vvh ? `${vvh}px` : '100dvh' }}
    >
      <header className="flex items-center gap-2 px-4 pt-3 pb-2">
        <Button variant="ghost" size="sm" onClick={onLeave}>
          <ArrowLeft aria-hidden />
          Leave
        </Button>
        <ProgressCounter className="min-w-0 flex-1" done={session.done} total={session.total} label="Cards finished" />
        <Button variant="ghost" size="sm" disabled={!interactive || !session.canUndo} onClick={() => void doUndo()}>
          <Undo2 aria-hidden />
          Undo
          <Kbd aria-hidden className="ml-1 hidden sm:inline-flex">
            U
          </Kbd>
        </Button>
        <Button variant="ghost" size="icon" aria-label="Keyboard shortcuts" onClick={() => setHelp(true)}>
          <Keyboard aria-hidden />
        </Button>
      </header>

      <div className="space-y-2 px-4">
        {session.offline || sync.pending > 0 || sync.last ? (
          <SyncStatus
            pending={sync.pending}
            syncing={sync.syncing}
            online={!session.offline}
            last={sync.last}
            onRetry={() => void sync.syncNow()}
          />
        ) : null}
        {session.staleWarning ? (
          <p
            role="status"
            className="rounded-lg border border-warning-border bg-warning-bg px-3 py-2 text-sm text-warning-fg"
          >
            These cards were downloaded more than 2 days ago. Some may have changed. Connect to refresh them.
          </p>
        ) : null}
        {session.quotaFull ? (
          <p
            role="alert"
            className="rounded-lg border border-warning-border bg-warning-bg px-3 py-2 text-sm text-warning-fg"
          >
            This device is holding as many reviews as it can keep. Connect to the internet to sync them, then carry on.
          </p>
        ) : null}
        {session.catchup ? (
          <p className="text-sm text-muted-foreground">
            Catch-up: the most important and most overdue cards come first.
          </p>
        ) : null}
      </div>

      <div className="flex min-h-0 flex-1 flex-col justify-center overflow-y-auto px-4 py-3">
        {!introDone ? (
          <FirstTimeIntro onDone={onIntroDone} />
        ) : card ? (
          <div className="space-y-3">
            {tricky ? (
              <p className="flex flex-wrap items-center gap-2 text-sm">
                <Badge variant="highlight">Tricky card</Badge>
                <span className="text-muted-foreground">
                  You have missed this one a few times. Rewording it can help.
                </span>
              </p>
            ) : null}
            <FlipCard
              key={card.id}
              flipped={flipped}
              onFlip={session.flip}
              showFlipButton={false}
              focusOnFlip
              swipeEnabled={session.gestures}
              onSwipe={(dir) => void session.rate(dir === 'right' ? 3 : 1)}
              label="Flashcard"
              front={<CardFace side="front" text={card.front} kind={card.kind} chapter={card.chapterName} />}
              back={<CardFace side="back" text={card.back} kind={card.kind} chapter={card.chapterName} />}
            />
            {flipped ? (
              <div className="flex flex-wrap justify-center gap-2">
                {edit ? (
                  <Button variant="ghost" size="sm" onClick={edit}>
                    Edit card
                  </Button>
                ) : null}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="sm">
                      Hold this card
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    <DropdownMenuItem disabled={session.offline} onSelect={() => void doHold('bury')}>
                      Bury until tomorrow
                    </DropdownMenuItem>
                    <DropdownMenuItem disabled={session.offline} onSelect={() => void doHold('suspend')}>
                      Suspend
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            ) : null}
          </div>
        ) : null}
        <p role="status" className="sr-only">
          {message}
        </p>
      </div>

      {introDone && card ? (
        <div className="border-t border-border bg-background px-4 pt-3 pb-[max(env(safe-area-inset-bottom),0.75rem)]">
          {flipped ? (
            <div className="space-y-2">
              <RatingButtons
                onRate={(r) => void session.rate(r)}
                previews={session.previews ?? undefined}
                shortcuts
                showKeys
              />
              <p className="text-center text-xs text-muted-foreground">
                Be honest: Again is fine. It tells the schedule what to show you sooner.
              </p>
            </div>
          ) : (
            <Button ref={showRef} size="lg" className="w-full" aria-keyshortcuts="Space Enter" onClick={session.flip}>
              Show answer
              <Kbd aria-hidden className="ml-2 hidden sm:inline-flex">
                Space
              </Kbd>
            </Button>
          )}
        </div>
      ) : null}
      <ShortcutsDialog open={help} onOpenChange={setHelp} />
    </div>
  )
}
