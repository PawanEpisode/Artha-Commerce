import { lazy, Suspense } from 'react'

import { ReaderLoading } from '../components/reader/ReaderLoading'
import type { PdfReaderContainerProps } from './PdfReaderContainer'

// The reader, the annotation layer, the engine adapter and pdf.js (with its worker) load as separate chunks, only when
// this route is opened. The module barrel exports this wrapper, never the screen itself, so no other screen pulls the
// reader into its bundle.
const Reader = lazy(() => import('./PdfReaderScreen').then((m) => ({ default: m.PdfReaderScreen })))

export function PdfReaderContainer(props: PdfReaderContainerProps) {
  return (
    <Suspense fallback={<ReaderLoading />}>
      <Reader {...props} />
    </Suspense>
  )
}
