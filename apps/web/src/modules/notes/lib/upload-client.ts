import {
  abortDocument,
  completeDocument,
  deleteDocument,
  getDocument,
  getProcessing,
  reserveDocument,
  uploadDocumentBytes,
} from './documents-api'
import { createUploadManager } from './upload-manager'

/**
 * The one upload manager of the tab, wired to the real API. Module level on purpose: it keeps running while the student
 * navigates, and every screen reads the same list through `useUploads`.
 */
export const uploadManager = createUploadManager({
  reserve: reserveDocument,
  send: (target, file, options) => uploadDocumentBytes(target, file, options),
  complete: completeDocument,
  abort: abortDocument,
  processing: getProcessing,
  document: getDocument,
  purge: (id) => deleteDocument(id, true),
  now: () => Date.now(),
  newId: () => crypto.randomUUID(),
  wait: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
})
