import { Alert, Button, Container, EmptyState, Notebook } from '@artha/design-system'
import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { ConflictSheet } from '../components/ConflictSheet'
import { NotesNav } from '../components/NotesNav'
import { useUsage } from '../hooks/useNotesQueries'
import { useNotesFlusher } from '../hooks/useNotesSync'
import { useParkedConflicts } from '../hooks/useParkedConflicts'
import { isFeatureDisabled } from '../lib/errors'
import { pluralize } from '../lib/format'

interface NotesChrome {
  /** Opens the sheet that settles the first parked conflict (the status chip and the banner both call it). */
  openConflicts: () => void
}

const ChromeContext = createContext<NotesChrome>({ openConflicts: () => undefined })
export const useNotesChrome = () => useContext(ChromeContext)

interface NotesShellProps {
  children: ReactNode
  /** Without the tabs and the page container: the editor draws its own. */
  bare?: boolean
  /** Export and delete never depend on the flag, so Settings passes the off state through instead of blocking. */
  allowWhenOff?: boolean
  width?: 'max-w-3xl' | 'max-w-4xl'
}

/**
 * The frame of every notes screen: the `notes` flag (web and server, fail open), the one queue flusher of this tab,
 * and the conflict sheet for edits the server could not merge. Children render when the feature is on.
 */
export function NotesShell({ children, bare = false, allowWhenOff = false, width = 'max-w-4xl' }: NotesShellProps) {
  const enabled = useFeatureFlag('notes')
  const usage = useUsage()
  const off = !enabled || isFeatureDisabled(usage.error)
  useNotesFlusher(!off)
  const { parked, busy, resolve } = useParkedConflicts()
  const [open, setOpen] = useState(false)
  const openConflicts = useCallback(() => setOpen(true), [])
  const chrome = useMemo(() => ({ openConflicts }), [openConflicts])
  const first = parked[0]

  if (off && !allowWhenOff) {
    return (
      <Container className="max-w-3xl py-14">
        <EmptyState
          icon={<Notebook aria-hidden />}
          title="Notes are not available yet"
          description="We are rolling them out gradually. Please check back soon."
        />
      </Container>
    )
  }

  const banner =
    parked.length > 0 ? (
      <Alert variant="info">
        <span className="flex flex-wrap items-center gap-3">
          <span>
            {pluralize(parked.length, 'note')} changed on two devices and need{parked.length === 1 ? 's' : ''} your
            choice.
          </span>
          <Button size="sm" variant="outline" onClick={openConflicts}>
            Settle now
          </Button>
        </span>
      </Alert>
    ) : null

  const sheet = first ? (
    <ConflictSheet
      open={open}
      onOpenChange={setOpen}
      theirs={first.detail.theirs}
      mine={{ title: first.detail.mine.title ?? first.detail.theirs.title, body: first.detail.mine.body_md ?? '' }}
      deviceLabel={first.detail.device_label}
      busy={busy}
      onResolve={(resolution) =>
        void resolve(first, resolution).then((ok) => ok && parked.length <= 1 && setOpen(false))
      }
    />
  ) : null

  return (
    <ChromeContext.Provider value={chrome}>
      {bare ? (
        <>
          {banner ? <Container className="max-w-5xl pt-6">{banner}</Container> : null}
          {children}
        </>
      ) : (
        <>
          <NotesNav />
          <Container className={`${width} space-y-6 py-8 sm:py-12`}>
            {banner}
            {children}
          </Container>
        </>
      )}
      {sheet}
    </ChromeContext.Provider>
  )
}
