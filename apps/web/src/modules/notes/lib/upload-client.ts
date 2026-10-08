import {
  abortDocument,
  completeDocument,
  deleteDocument,
  finishResumable,
  getDocument,
  getProcessing,
  putPart,
  reserveDocument,
  reserveReplacement,
  signParts,
  startResumable,
  uploadDocumentBytes,
} from './documents-api'
import { uploadInParts } from './resumable-upload'
import { createUploadManager } from './upload-manager'

/**
 * The one upload manager of the tab, wired to the real API. Module level on purpose: it keeps running while the student
 * navigates, and every screen reads the same list through `useUploads`.
 */
export const uploadManager = createUploadManager({
  reserve: (body, replaces) => (replaces ? reserveReplacement(replaces, body) : reserveDocument(body)),
  send: (target, file, options) =>
    target.resumable
      ? uploadInParts(
          {
            start: startResumable,
            sign: signParts,
            put: putPart,
            finish: finishResumable,
            wait: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
          },
          target.resumable,
          file,
          options,
        )
      : uploadDocumentBytes(target, file, options),
  complete: completeDocument,
  abort: abortDocument,
  processing: getProcessing,
  document: getDocument,
  purge: (id) => deleteDocument(id, true),
  now: () => Date.now(),
  newId: () => crypto.randomUUID(),
  wait: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
})
