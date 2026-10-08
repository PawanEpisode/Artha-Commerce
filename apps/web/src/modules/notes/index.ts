// Public surface of the notes module. Other modules import from here only.
export { type PdfPageContextValue, usePdfPageContext } from './components/reader/PdfPageContext'
export { ChapterNotesContainer } from './containers/ChapterNotesContainer'
export { ChapterNotesSlot } from './containers/ChapterNotesSlot'
export { LibraryContainer } from './containers/LibraryContainer'
export { NewNoteContainer } from './containers/NewNoteContainer'
export { NoteEditorContainer } from './containers/NoteEditorContainer'
export { NotesHubContainer } from './containers/NotesHubContainer'
export { NotesSearchContainer } from './containers/NotesSearchContainer'
export { NotesSettingsContainer } from './containers/NotesSettingsContainer'
export { NotesTrashContainer } from './containers/NotesTrashContainer'
export type { PdfReaderContainerProps } from './containers/PdfReaderContainer'
export { PdfReaderContainer } from './containers/PdfReaderLazy'
export type { ReaderApi, ReaderExtensions } from './containers/reader-extensions'
export { SaveToNotes, type SaveToNotesProps } from './containers/SaveToNotes'
export { SubjectNotesContainer } from './containers/SubjectNotesContainer'
export { UploadProgressContainer } from './containers/UploadProgressContainer'
export {
  useDocument,
  useDocumentProcessing,
  useInDocumentSearch,
  usePageText,
  useUpdateProgress,
} from './hooks/useDocuments'
export { useChapterNotesOverview } from './hooks/useNotesQueries'
export { useReaderOcrExport } from './hooks/useReaderOcrExport'
export { useUploads } from './hooks/useUploads'
export { clearAnnotationData } from './lib/annotation-store'
export type { Annotation, MarkKind, MarkRecord } from './lib/annotation-types'
export type {
  Document,
  DocumentDetail,
  DocumentProcessing,
  DocumentStatus,
  DocumentSummary,
  OcrStatus,
  OutlineNode,
  PageRange,
  PageSize,
  PageTone,
} from './lib/document-types'
export { documentErrorMessage, documentQuotaExceeded } from './lib/errors'
export { newNoteSchema, noteEditorSchema, noteFilterSchema, noteSearchSchema } from './lib/filter-schema'
export { isLargeDocument } from './lib/large-document'
export { type LibrarySearch, librarySearchSchema } from './lib/library-schema'
export { clearNotesLocalData } from './lib/local-data'
export { markOpenedFrom, type OpenedFrom } from './lib/opened-from'
export type { PageSelection } from './lib/pdf-engine/text-layer'
export { READER_PANELS, READER_TOOLS, type ReaderSearch, readerSearchSchema, type ZoomSpec } from './lib/reader-schema'
export type { ChapterOverview, ClipSource } from './lib/types'
