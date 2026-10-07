import type { RefObject } from 'react'
import { useCallback, useEffect, useState } from 'react'

import { MarkToolbar } from '../components/annotations/MarkToolbar'
import { SelectionToolbar } from '../components/annotations/SelectionToolbar'
import { inkOptions } from '../lib/annotation-legend'
import { geometryBbox } from '../lib/geometry'
import { useUiScope } from './annotation-scope'

const SCROLLER = '[data-slot="pdf-viewport"]'

/** The text selection's rectangle on screen, read fresh on every scroll. */
const selectionRect = () => {
  const sel = window.getSelection()
  if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return null
  return sel.getRangeAt(0).getBoundingClientRect()
}

/** The bar at a text selection: five named colours, underline, Note, Card and Copy. */
export function SelectionToolbarContainer({ viewport }: { viewport: RefObject<HTMLElement | null> }) {
  const ui = useUiScope()
  const [scroller, setScroller] = useState<Element | null>(null)
  useEffect(() => setScroller(document.querySelector(SCROLLER)), [])
  if (!ui) return null
  const { selection, settings, selectionActions } = ui
  const open = !!selection && !ui.tool && !ui.edit
  const defaultName = settings.options.find((o) => o.key === ui.markupColor)?.name
  return (
    <SelectionToolbar
      open={open}
      onOpenChange={(next) => !next && selectionActions.dismiss()}
      anchor={selectionRect}
      scrollContainer={scroller}
      returnFocusRef={viewport}
      options={settings.options}
      color={ui.markupColor}
      canCard={settings.canCard}
      cardDisabledReason={ui.marks.online ? undefined : 'Cards need a connection.'}
      cardKindName={defaultName}
      onColor={selectionActions.color}
      onUnderline={selectionActions.underline}
      onNote={selectionActions.note}
      onCard={selectionActions.card}
      onCopy={selectionActions.copy}
    />
  )
}

/** The bar over the selected mark: colour, edit, card, delete. */
export function MarkToolbarContainer({ viewport }: { viewport: RefObject<HTMLElement | null> }) {
  const ui = useUiScope()
  const [scroller, setScroller] = useState<Element | null>(null)
  useEffect(() => setScroller(document.querySelector(SCROLLER)), [])
  const mark = ui?.selectedMark ?? null
  const anchor = useCallback(() => {
    if (!mark) return null
    const page = document.querySelector<HTMLElement>(`[data-page="${mark.page}"]`)
    if (!page) return null
    const box = page.getBoundingClientRect()
    const [x, y, w, h] = geometryBbox(mark.kind, mark.geometry)
    const left = box.left + (mark.kind === 'bookmark' ? 0 : x) * box.width
    const top = box.top + y * box.height
    const width = mark.kind === 'bookmark' ? 28 : Math.max(24, w * box.width)
    return new DOMRect(left, top, width, Math.max(24, h * box.height))
  }, [mark])
  if (!ui || !mark || ui.tool || ui.edit) return null
  const ink = mark.kind === 'ink' || mark.kind === 'textbox'
  return (
    <MarkToolbar
      open
      onOpenChange={(next) => !next && ui.markActions.dismiss()}
      anchor={anchor}
      scrollContainer={scroller}
      returnFocusRef={viewport}
      options={mark.kind === 'bookmark' ? [] : ink ? inkOptions() : ui.settings.options}
      color={mark.color}
      canCard={
        ui.settings.canCard && (mark.kind === 'highlight' || mark.kind === 'underline' || mark.kind === 'sticky')
      }
      hasCard={mark.recall_card_id !== null}
      onColor={ui.markActions.color}
      onEdit={ui.markActions.edit}
      onCard={ui.markActions.card}
      onDelete={ui.markActions.remove}
    />
  )
}
