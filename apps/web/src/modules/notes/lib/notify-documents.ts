import { toast, toastApiError } from '@artha/design-system'

import { documentErrorMessage } from './errors'
import { UNDO_MS } from './notify'

/** Words for every PDF outcome that is a toast. Titles and file names never go into analytics, only into what the student sees. */
const ID = { trash: 'docs-trash', upload: 'docs-upload', ocr: 'docs-ocr', export: 'docs-export' } as const

export const notifyDocs = {
  trashed: (onUndo: () => void) =>
    toast.info('Moved to Trash', {
      id: ID.trash,
      description: 'Kept for 30 days. The space is freed when it is deleted for good.',
      duration: UNDO_MS,
      action: { label: 'Undo', onClick: onUndo },
    }),
  restored: () => toast.success('PDF restored'),
  purged: (freed: string) => toast.success('PDF deleted for good', { description: `${freed} freed.` }),
  saved: () => toast.success('Details saved'),
  rangesSaved: (relinked: number) =>
    toast.success('Page ranges saved', {
      description:
        relinked > 0 ? `${relinked} mark${relinked === 1 ? '' : 's'} moved to the right chapter.` : undefined,
    }),

  added: (onOpen: () => void) =>
    toast.success('PDF added', { id: ID.upload, action: { label: 'Open', onClick: onOpen } }),
  addedScanned: (onOpen: () => void) =>
    toast.success('Scanned PDF added', {
      id: ID.upload,
      description: 'It opens now. Search and text selection need OCR.',
      action: { label: 'Open', onClick: onOpen },
    }),
  addedLocked: (onOpen: () => void) =>
    toast.success('Locked PDF added', {
      id: ID.upload,
      description: 'It opens with your password. Search and OCR need it.',
      action: { label: 'Open', onClick: onOpen },
    }),

  ocrStarted: (minutes: string) =>
    toast.info('Making your PDF searchable', {
      id: ID.ocr,
      description: `${minutes}. Pages become searchable as they finish, and you can keep reading.`,
    }),
  alreadySearchable: () =>
    toast.success('Already searchable', { id: ID.ocr, description: 'This file was read before.' }),
  ocrDone: (onOpen?: () => void) =>
    toast.success('Your PDF is searchable', {
      id: ID.ocr,
      ...(onOpen ? { action: { label: 'Open', onClick: onOpen } } : {}),
    }),
  ocrQuota: () =>
    toast.warning('Not enough OCR pages left this month', {
      id: ID.ocr,
      description: 'Open the PDF to read just the first pages, or wait for the monthly reset.',
    }),
  ocrFailed: () =>
    toast.warning('We could not finish making the PDF searchable', {
      id: ID.ocr,
      description: 'Open it to try again.',
    }),

  exportReady: () =>
    toast.success('Your export is ready', { id: ID.export, description: 'The link works for 24 hours.' }),

  error: (error: unknown, fallback: string) => toastApiError(error, documentErrorMessage(error) || fallback),
}
