import {
  Button,
  SelectField,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  TextField,
  Trash2,
} from '@artha/design-system'
import { type ReactNode, useState } from 'react'

import type { DocumentDetail, SourceKind } from '../../lib/document-types'
import { SOURCE_KINDS, SOURCE_LABEL } from '../../lib/library-schema'
import type { Tag } from '../../lib/types'
import { TagEditor } from '../TagEditor'

export interface DetailsDraft {
  title: string
  source_kind: SourceKind
  edition_label: string
  tag_ids: string[]
}

interface DocumentDetailsSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  doc: DocumentDetail
  tags: readonly Tag[]
  onCreateTag: (name: string) => Promise<Tag | undefined>
  /** The default-chapter button (the F-02 picker). */
  chapterSlot: ReactNode
  /** The page-range editor. */
  rangesSlot: ReactNode
  /** Replace edition (R3); nothing when the feature is off. */
  replaceSlot?: ReactNode
  saving: boolean
  onSave: (draft: DetailsDraft) => void
  onTrash: () => void
  onDeleteNow: () => void
  online: boolean
}

const PRIVATE_KINDS = new Set<SourceKind>(['coaching', 'institute_material'])

/**
 * Edit a PDF's details: title, where it came from, edition, default chapter, tags and page ranges, and the two ways to get
 * rid of it (Trash with Undo, or Delete now). The form keeps its own draft; Save sends only what changed.
 */
export function DocumentDetailsSheet({
  open,
  onOpenChange,
  doc,
  tags,
  onCreateTag,
  chapterSlot,
  rangesSlot,
  replaceSlot,
  saving,
  onSave,
  onTrash,
  onDeleteNow,
  online,
}: DocumentDetailsSheetProps) {
  const [draft, setDraft] = useState<DetailsDraft>({
    title: doc.title,
    source_kind: doc.source_kind,
    edition_label: doc.edition_label ?? '',
    tag_ids: doc.tags.map((t) => t.id),
  })
  const titleMissing = draft.title.trim() === ''
  const isPrivate = PRIVATE_KINDS.has(draft.source_kind)
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="max-h-[92dvh] overflow-y-auto sm:mx-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>Edit details</SheetTitle>
          <SheetDescription className="break-words">{doc.original_filename}</SheetDescription>
        </SheetHeader>
        <div className="space-y-6">
          <TextField
            label="Title"
            value={draft.title}
            maxLength={200}
            error={titleMissing ? 'Give the PDF a title.' : undefined}
            onChange={(e) => setDraft({ ...draft, title: e.target.value })}
          />

          <div className="grid gap-2">
            <label htmlFor="doc-source" className="text-sm font-semibold">
              Where is it from?
            </label>
            <SelectField
              id="doc-source"
              value={draft.source_kind}
              onValueChange={(value) => setDraft({ ...draft, source_kind: value as SourceKind })}
              options={SOURCE_KINDS.map((k) => ({ value: k, label: SOURCE_LABEL[k] }))}
            />
            <p className="text-sm text-muted-foreground">
              {isPrivate ? (
                <>
                  <strong className="font-semibold text-foreground">Private to you.</strong> Coaching and institute
                  material is never shared: only your own notes and marks can be shared later.
                </>
              ) : (
                'Only your own notes and marks can be shared later, never the PDF itself.'
              )}
            </p>
          </div>

          <TextField
            label="Edition (optional)"
            hint="For example: May 2027 attempt, 2nd edition."
            value={draft.edition_label}
            maxLength={60}
            onChange={(e) => setDraft({ ...draft, edition_label: e.target.value })}
          />

          <div className="grid gap-2">
            <span className="text-sm font-semibold">Default chapter</span>
            {chapterSlot}
            <p className="text-sm text-muted-foreground">Marks on pages with no range of their own are filed here.</p>
          </div>

          <div className="grid gap-2">
            <span className="text-sm font-semibold">Tags</span>
            <TagEditor
              tags={tags}
              selectedIds={draft.tag_ids}
              onChange={(tag_ids) => setDraft({ ...draft, tag_ids })}
              onCreate={onCreateTag}
              createDisabledReason={online ? undefined : 'New tags need a connection.'}
            />
          </div>

          {rangesSlot}
          {replaceSlot}
        </div>

        <SheetFooter className="mt-6">
          <Button variant="ghost" onClick={onTrash} disabled={!online}>
            <Trash2 aria-hidden /> Move to Trash
          </Button>
          <Button variant="danger" onClick={onDeleteNow} disabled={!online}>
            Delete now
          </Button>
          <Button onClick={() => onSave(draft)} disabled={titleMissing || saving || !online} loading={saving}>
            Save details
          </Button>
        </SheetFooter>
        {!online ? (
          <p className="mt-2 text-sm text-muted-foreground">You are offline. Changes need a connection.</p>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
