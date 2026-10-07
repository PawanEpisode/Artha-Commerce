import { useMemo } from 'react'

import { useAnnotationExtensions } from '../hooks/useAnnotationExtensions'
import { useReaderOcrExport } from '../hooks/useReaderOcrExport'
import { AnnotationProvider } from './annotation-scope'
import { mergeExtensions } from './merge-extensions'
import { PdfReaderContainer, type PdfReaderContainerProps } from './PdfReaderContainer'

/**
 * `/app/notes/pdf/$docId`: the reader with everything plugged in. The annotation layer (marks, tools, list, sync) and the
 * library's export and OCR seams are merged into the reader's extension points; the reader itself knows none of them.
 * The reader element is memoised on what it is given, so a text selection or a sheet opening redraws only the pieces that
 * read the annotation context, never the pages.
 */
export function PdfReaderScreen(props: PdfReaderContainerProps) {
  const { docId, search, onSearchChange, onBack, engine, extensions: given, onMakeSearchable } = props
  const annotations = useAnnotationExtensions({ docId, search, onSearchChange })
  const library = useReaderOcrExport(docId)
  const libraryExtensions = library.extensions
  const extensions = useMemo(
    () => mergeExtensions(given, libraryExtensions, annotations.extensions),
    [given, libraryExtensions, annotations.extensions],
  )
  const searchable = library.onMakeSearchable ?? onMakeSearchable
  const reader = useMemo(
    () => (
      <PdfReaderContainer
        docId={docId}
        search={search}
        onSearchChange={onSearchChange}
        onBack={onBack}
        engine={engine}
        extensions={extensions}
        onMakeSearchable={searchable}
      />
    ),
    [docId, search, onSearchChange, onBack, engine, extensions, searchable],
  )
  return (
    <AnnotationProvider page={annotations.page} ui={annotations.ui}>
      {reader}
    </AnnotationProvider>
  )
}
