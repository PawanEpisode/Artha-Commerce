import { useEffect, useRef } from 'react'

import { useUiScope } from './annotation-scope'
import { AnnotationEditContainer } from './AnnotationEditContainer'
import { AnnotationListContainer } from './AnnotationListContainer'
import { MarkToolbarContainer, SelectionToolbarContainer } from './AnnotationToolbars'
import { MarkConflictContainer } from './MarkConflictContainer'
import type { ReaderApi } from './reader-extensions'

/**
 * Floating pieces over the reading area (the reader's `viewportOverlay` slot): the selection and mark toolbars, the edit
 * and conflict sheets and the phone's list sheet. It also hands the reader's API (page, `goToPage`, the open file) to the
 * annotation layer's handlers.
 */
export function AnnotationViewportOverlay({ api }: { api: ReaderApi }) {
  const ui = useUiScope()
  const viewport = useRef<HTMLElement | null>(null)
  const apiRef = ui?.apiRef
  useEffect(() => {
    if (apiRef) apiRef.current = api
  })
  const onPage = ui?.onPage
  const page = api.page
  useEffect(() => onPage?.(page), [onPage, page])
  useEffect(() => {
    viewport.current = document.querySelector<HTMLElement>('[data-slot="pdf-viewport"]')
  }, [])
  if (!ui) return null
  return (
    <>
      <SelectionToolbarContainer viewport={viewport} />
      <MarkToolbarContainer viewport={viewport} />
      {ui.edit ? <AnnotationEditContainer /> : null}
      <MarkConflictContainer />
      {!ui.docked ? <AnnotationListContainer /> : null}
    </>
  )
}

/** The wide-screen list, docked beside the page (the reader's `sidePanel` slot). */
export function AnnotationSidePanel() {
  const ui = useUiScope()
  if (!ui || !ui.docked) return null
  return <AnnotationListContainer />
}
