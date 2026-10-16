import {
  Alert,
  ArrowLeft,
  Button,
  History,
  Page,
  Pin,
  PinOff,
  SyncChip,
  type SyncState,
  Trash2,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { type PickedImage, RichTextEditor } from '~/lib/richtext'

import type { SaveProblem } from '../hooks/useNoteEditor'
import { pluralize } from '../lib/format'
import { UNSYNCED_TEXT } from '../lib/sync-state'

interface NoteEditorViewProps {
  title: string
  onTitle: (value: string) => void
  body: string
  onBody: (value: string) => void
  /** The note exists only on this device and waits to sync: say so next to the status chip. */
  localOnly: boolean
  sync: { state: SyncState; count: number }
  onSyncPress?: () => void
  /** "Last saved 4:30 pm", or nothing before the first save. */
  savedText?: string
  recovered: boolean
  onDiscardRecovered: () => void
  problems: SaveProblem | null
  saveFailed: boolean
  overBy: number
  maxChars: number
  online: boolean
  pinned?: boolean
  onPin?: () => void
  onTrash?: () => void
  onHistory?: () => void
  onSave: () => void
  onPickImage: () => Promise<PickedImage | null>
  resolveImage?: (id: string) => string | undefined
  /** Where the note is filed, and its tags: containers provide the controls. */
  linkControl: ReactNode
  tagsControl: ReactNode
  /** Sheets and dialogs that belong to the screen. */
  overlays?: ReactNode
  /** A notice above the title (a note in the Trash). */
  banner?: ReactNode
  readOnly?: boolean
}

/**
 * The editor screen: title, the Markdown editor with its live preview, where the note is filed, tags, and the save
 * status. All text and actions are props; the container owns saving, drafts and conflicts.
 */
export function NoteEditorView(p: NoteEditorViewProps) {
  return (
    <Page className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/app/notes">
            <ArrowLeft aria-hidden /> All notes
          </Link>
        </Button>
        <div className="flex flex-wrap items-center gap-2">
          <SyncChip
            state={p.sync.state}
            count={p.sync.count}
            onPress={p.sync.state === 'attention' ? p.onSyncPress : undefined}
          />
          {p.localOnly ? (
            <span className="text-xs text-muted-foreground">{UNSYNCED_TEXT}</span>
          ) : p.savedText ? (
            <span className="text-xs text-muted-foreground">{p.savedText}</span>
          ) : null}
          <Button onClick={p.onSave} disabled={p.overBy > 0 || p.readOnly}>
            Save now
          </Button>
        </div>
      </div>

      {p.recovered ? (
        <Alert variant="info">
          <span className="flex flex-wrap items-center gap-3">
            <span>
              <strong>Recovered draft.</strong> We restored the text you were writing on this device.
            </span>
            <Button size="sm" variant="outline" onClick={p.onDiscardRecovered}>
              Discard draft
            </Button>
          </span>
        </Alert>
      ) : null}
      {p.banner}

      <div className="grid items-start gap-x-6 gap-y-4 lg:grid-cols-[minmax(0,48rem)_20rem]">
        <div className="min-w-0 space-y-3">
          <div>
            <label htmlFor="note-title" className="sr-only">
              Title
            </label>
            <input
              id="note-title"
              value={p.title}
              maxLength={200}
              placeholder="Untitled note"
              readOnly={p.readOnly}
              onChange={(e) => p.onTitle(e.target.value)}
              className="h-10 w-full rounded-md border border-input bg-card px-3 text-lg font-semibold tracking-tight outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
            />
          </div>

          <RichTextEditor
            value={p.body}
            onChange={p.onBody}
            label="Note text"
            profile="note"
            readOnly={p.readOnly}
            placeholder="Write in Markdown. Use the toolbar for headings, lists, tables and formulas."
            onPickImage={p.onPickImage}
            imageDisabledReason={p.online ? undefined : 'Images need a connection'}
            resolveImage={p.resolveImage}
            describedBy="note-problems"
          />

          <div id="note-problems" className="space-y-2" aria-live="polite">
            {p.overBy > 0 ? (
              <Alert variant="error">
                <span>
                  This note is {pluralize(p.overBy, 'character')} over the {p.maxChars.toLocaleString('en-IN')}{' '}
                  character limit. Shorten it or move part of it to a new note. It is kept on this device until it fits.
                </span>
              </Alert>
            ) : null}
            {p.problems?.kind === 'lint' ? (
              <Alert variant="error">
                <div>
                  <p className="font-semibold">
                    Fix these before the note can be saved. Your text is kept on this device.
                  </p>
                  <ul className="mt-1 list-disc pl-5">
                    {p.problems.issues.slice(0, 5).map((issue, index) => (
                      <li key={index}>
                        {issue.line ? `Line ${issue.line}: ` : ''}
                        {issue.message}
                      </li>
                    ))}
                  </ul>
                </div>
              </Alert>
            ) : null}
            {p.problems?.kind === 'server' ? (
              <Alert variant="error">
                <div>
                  <p className="font-semibold">The server could not accept this text.</p>
                  <ul className="mt-1 list-disc pl-5">
                    {p.problems.errors.slice(0, 5).map((error, index) => (
                      <li key={index}>
                        {error.line ? `Line ${error.line}: ` : ''}
                        {error.message}
                      </li>
                    ))}
                  </ul>
                </div>
              </Alert>
            ) : null}
            {p.saveFailed ? (
              <Alert variant="error">
                <span>We could not save just now. Your text is safe on this device and we will try again.</span>
              </Alert>
            ) : null}
          </div>
        </div>

        <aside
          aria-label="Note details"
          className="min-w-0 divide-y rounded-lg border bg-card lg:sticky lg:top-[calc(var(--site-header-height,2.75rem)+1rem)]"
        >
          <section className="space-y-2 p-3">
            <h2 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Filed under</h2>
            {p.linkControl}
          </section>
          <section aria-labelledby="note-tags-h" className="space-y-2 p-3">
            <h2 id="note-tags-h" className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Tags
            </h2>
            {p.tagsControl}
          </section>
          {p.onPin || p.onHistory || p.onTrash ? (
            <section aria-label="Note actions" className="flex flex-wrap items-center gap-1.5 p-3">
              {p.onPin ? (
                <Button variant="outline" size="sm" aria-pressed={p.pinned} onClick={p.onPin}>
                  {p.pinned ? <PinOff aria-hidden /> : <Pin aria-hidden />}
                  {p.pinned ? 'Unpin' : 'Pin'}
                </Button>
              ) : null}
              {p.onHistory ? (
                <Button variant="outline" size="sm" onClick={p.onHistory}>
                  <History aria-hidden /> History
                </Button>
              ) : null}
              {p.onTrash ? (
                <Button variant="ghost" size="sm" onClick={p.onTrash}>
                  <Trash2 aria-hidden /> Move to Trash
                </Button>
              ) : null}
            </section>
          ) : null}
        </aside>
      </div>
      {p.overlays}
    </Page>
  )
}
