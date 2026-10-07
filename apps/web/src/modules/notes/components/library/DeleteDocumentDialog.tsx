import { Button, Dialog, DialogContent, DialogDescription, DialogTitle } from '@artha/design-system'

import { formatBytes } from '../../lib/format'

interface DeleteDocumentDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  doc: { title: string; bytes: number } | null
  busy: boolean
  onConfirm: () => void
}

/** "Delete now": permanent, and says how much space it frees (FR-F03-07). The gentler way is Move to Trash, with Undo. */
export function DeleteDocumentDialog({ open, onOpenChange, doc, busy, onConfirm }: DeleteDocumentDialogProps) {
  return (
    <Dialog open={open && doc !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Delete this PDF for good?</DialogTitle>
        <DialogDescription className="break-words">
          {doc?.title}. This removes the PDF and all your marks on it. It cannot be undone.
          {doc ? ` It frees ${formatBytes(doc.bytes)} of your PDF storage right away.` : ''}
        </DialogDescription>
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={busy}>
            Keep it
          </Button>
          <Button variant="danger" onClick={onConfirm} loading={busy}>
            Delete now
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
