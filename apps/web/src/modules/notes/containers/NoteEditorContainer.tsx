import { Alert, Button, Container, EmptyState, Notebook, Skeleton } from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useMemo, useState } from 'react'

import { attachmentRefs } from '~/lib/richtext'

import { ConflictSheet } from '../components/ConflictSheet'
import { ImagePickerDialog } from '../components/ImagePickerDialog'
import { NoteEditorView } from '../components/NoteEditorView'
import { SuggestionBar } from '../components/SuggestionBar'
import { TagEditor } from '../components/TagEditor'
import { type VersionMode, VersionPanel } from '../components/VersionPanel'
import { useAttachmentUrls } from '../hooks/useAttachmentUrls'
import { useImagePicker } from '../hooks/useImagePicker'
import { useNoteActions } from '../hooks/useNoteActions'
import { useNoteEditor } from '../hooks/useNoteEditor'
import { useChapterSuggestions, useLevelId, useTags, useVersion, useVersions } from '../hooks/useNotesQueries'
import { useSyncView } from '../hooks/useNotesSync'
import { selectionFromSuggestion } from '../lib/chapter-link'
import type { NoteEditorSearch } from '../lib/filter-schema'
import { formatTime } from '../lib/format'
import { showUnsynced } from '../lib/sync-state'
import { ChapterPicker } from './ChapterPicker'
import { NotesShell, useNotesChrome } from './NotesShell'

function EditorStates({ status, onRetry }: { status: 'loading' | 'error' | 'notfound'; onRetry: () => void }) {
  if (status === 'loading') {
    return (
      <Container className="max-w-5xl space-y-4 py-10">
        <div aria-busy="true" className="space-y-4">
          <span role="status" className="sr-only">
            Opening your note…
          </span>
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-80 w-full" />
        </div>
      </Container>
    )
  }
  if (status === 'notfound') {
    return (
      <Container className="max-w-3xl py-14">
        <EmptyState
          icon={<Notebook aria-hidden />}
          title="This note could not be found"
          description="It may have been deleted for good, or it belongs to another account."
          action={
            <Button asChild>
              <Link to="/app/notes">Back to my notes</Link>
            </Button>
          }
        />
      </Container>
    )
  }
  return (
    <Container className="max-w-3xl py-14">
      <Alert variant="error">
        <span className="flex flex-wrap items-center gap-3">
          <span>We could not open this note.</span>
          <Button size="sm" variant="outline" onClick={onRetry}>
            Try again
          </Button>
        </span>
      </Alert>
    </Container>
  )
}

interface ScreenProps {
  noteId: string
  search?: NoteEditorSearch
}

function EditorScreen({ noteId, search }: ScreenProps) {
  const navigate = useNavigate()
  const chrome = useNotesChrome()
  const levelId = useLevelId()
  const actions = useNoteActions()
  const tags = useTags()
  const picker = useImagePicker()
  const editor = useNoteEditor({ noteId })
  const sync = useSyncView(editor.saving)
  const [mode, setMode] = useState<VersionMode>('view')
  const [restoring, setRestoring] = useState(false)

  const note = editor.note
  const panelOpen = search?.panel === 'history' || search?.v !== undefined
  const versions = useVersions(noteId, panelOpen && editor.online && !editor.localOnly)
  const version = useVersion(noteId, panelOpen && !editor.localOnly ? search?.v : undefined)

  const imageIds = useMemo(
    () => [
      ...new Set(
        [...attachmentRefs(editor.body), ...attachmentRefs(version.data?.body_md ?? '')].map((r) => r.attachmentId),
      ),
    ],
    [editor.body, version.data?.body_md],
  )
  const resolveImage = useAttachmentUrls(imageIds, editor.online)

  const unfiled = !editor.selection && !(note && note.link.chapter_id)
  const suggestions = useChapterSuggestions(noteId, `${editor.title}\n${editor.body}`, unfiled && !editor.localOnly)

  if (editor.status !== 'ready') return <EditorStates status={editor.status} onRetry={() => void editor.refetch()} />

  const setPanel = (next: { panel?: 'history'; v?: number }) =>
    void navigate({ to: '/app/notes/n/$noteId', params: { noteId }, search: next, replace: true })

  const trashed = Boolean(note?.deleted_at)
  const link = note?.link ?? {
    level_id: null,
    subject_id: null,
    subject_key: null,
    subject_name: null,
    chapter_id: null,
    chapter_key: null,
    chapter_name: null,
    topic_id: null,
    topic_key: null,
    topic_name: null,
    moved_or_removed: false,
  }

  return (
    <NoteEditorView
      title={editor.title}
      onTitle={editor.setTitle}
      body={editor.body}
      onBody={editor.setBody}
      localOnly={showUnsynced(note)}
      sync={sync}
      onSyncPress={chrome.openConflicts}
      savedText={editor.savedAt ? `Saved ${formatTime(new Date(editor.savedAt).toISOString())}` : undefined}
      recovered={editor.recovered}
      onDiscardRecovered={() => void editor.discardRecovered()}
      problems={editor.problems}
      saveFailed={editor.saveFailed}
      overBy={editor.overBy}
      maxChars={editor.maxChars}
      online={editor.online}
      readOnly={trashed}
      pinned={note?.pinned}
      onPin={note && !trashed ? () => void actions.pin(note, !note.pinned) : undefined}
      onTrash={
        note && !trashed
          ? () =>
              void actions.trash(note).then((ok) => {
                if (ok) void navigate({ to: '/app/notes' })
              })
          : undefined
      }
      onHistory={editor.localOnly ? undefined : () => setPanel({ panel: 'history' })}
      onSave={() => void editor.saveNow()}
      onPickImage={picker.onPickImage}
      resolveImage={resolveImage}
      banner={
        trashed && note ? (
          <Alert variant="info">
            <span className="flex flex-wrap items-center gap-3">
              This note is in the Trash.
              <Button size="sm" variant="outline" disabled={!editor.online} onClick={() => void actions.restore(note)}>
                Restore it
              </Button>
            </span>
          </Alert>
        ) : null
      }
      linkControl={
        <div className="flex min-w-0 flex-col gap-2">
          <ChapterPicker
            link={link}
            selection={editor.localOnly ? editor.selection : undefined}
            disabled={trashed}
            onSelect={(selection) => void editor.setSelection(selection)}
          />
          {unfiled && (suggestions.data?.length ?? 0) > 0 && levelId ? (
            <SuggestionBar
              suggestions={suggestions.data ?? []}
              onPick={(s) => void editor.setSelection(selectionFromSuggestion(s, levelId), 'suggestion')}
              onOther={() => undefined}
            />
          ) : null}
        </div>
      }
      tagsControl={
        note ? (
          <TagEditor
            tags={tags.data ?? []}
            selectedIds={note.tags.map((t) => t.id)}
            onChange={(ids) =>
              void actions.change(note, {
                tagIds: ids,
                tags: (tags.data ?? [])
                  .filter((t) => ids.includes(t.id))
                  .map((t) => ({ id: t.id, name: t.name, color_key: t.color_key })),
              })
            }
            onCreate={actions.addTag}
            createDisabledReason={editor.online ? undefined : 'Making a tag needs a connection.'}
          />
        ) : null
      }
      overlays={
        <>
          <ImagePickerDialog {...picker.dialog} />
          {note && !editor.localOnly ? (
            <VersionPanel
              open={panelOpen}
              onOpenChange={(open) => !open && setPanel({})}
              versions={versions.data}
              isPending={versions.isPending && editor.online}
              isError={versions.isError || !editor.online}
              onRetry={() => void versions.refetch()}
              currentRev={note.rev}
              currentBody={editor.body}
              selectedRev={search?.v}
              onSelect={(rev) => setPanel({ panel: 'history', v: rev })}
              detail={version.data}
              detailPending={version.isPending}
              mode={mode}
              onMode={setMode}
              restoring={restoring}
              online={editor.online}
              resolveImage={resolveImage}
              onRestore={async (v) => {
                setRestoring(true)
                const restored = await actions.restoreOldVersion(note.id, v.rev, v.created_at)
                setRestoring(false)
                if (restored) setPanel({})
              }}
            />
          ) : null}
          {editor.conflict ? (
            <ConflictSheet
              open
              onOpenChange={() => undefined}
              theirs={editor.conflict.detail.theirs}
              mine={editor.conflict.mine}
              deviceLabel={editor.conflict.detail.device_label}
              busy={editor.resolving}
              onResolve={(resolution) => void editor.resolveConflict(resolution)}
            />
          ) : null}
        </>
      }
    />
  )
}

export function NoteEditorContainer({ noteId, search }: { noteId: string; search: NoteEditorSearch }) {
  return (
    <NotesShell bare>
      <EditorScreen key={noteId} noteId={noteId} search={search} />
    </NotesShell>
  )
}
