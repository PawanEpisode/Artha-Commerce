import {
  Copy,
  FloatingToolbar,
  type FloatingToolbarAnchor,
  FloatingToolbarButton,
  FloatingToolbarSeparator,
  Layers,
  StickyNote,
  type SwatchKey,
  type SwatchOption,
  SwatchPicker,
  Underline,
} from '@artha/design-system'
import type { RefObject } from 'react'

import type { MarkupColor } from '../../lib/annotation-types'

export interface SelectionToolbarProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Where the selected text is, in viewport coordinates (read again on scroll). */
  anchor: FloatingToolbarAnchor
  scrollContainer?: Element | null
  returnFocusRef?: RefObject<HTMLElement | null>
  /** The five colours with the student's own names ("Formula", "Doubt"). */
  options: SwatchOption[]
  /** The colour used by `h`; shown as checked. */
  color: MarkupColor
  /** Shown only when the server says a recall provider exists. */
  canCard: boolean
  /** Why the card button cannot be used right now (offline). */
  cardDisabledReason?: string
  /** "Formula" when the default colour is named that: the card type follows the legend (FR-F03-28). */
  cardKindName?: string
  onColor: (key: MarkupColor) => void
  onUnderline: () => void
  onNote: () => void
  onCard: () => void
  onCopy: () => void
}

const TARGET = 'size-11 min-h-11 min-w-11 sm:size-11'

/**
 * The bar that appears at a text selection: five named colour dots (one tap saves the highlight), underline, Note, Card
 * (hidden without a recall provider) and Copy. It does not take focus from the page; F10 moves into it, Escape closes it.
 */
export function SelectionToolbar({
  open,
  onOpenChange,
  anchor,
  scrollContainer,
  returnFocusRef,
  options,
  color,
  canCard,
  cardDisabledReason,
  cardKindName,
  onColor,
  onUnderline,
  onNote,
  onCard,
  onCopy,
}: SelectionToolbarProps) {
  return (
    <FloatingToolbar
      open={open}
      onOpenChange={onOpenChange}
      anchor={anchor}
      scrollContainer={scrollContainer}
      returnFocusRef={returnFocusRef}
      label="Mark the selected text"
      side="top"
    >
      <SwatchPicker
        label="Highlight colour"
        options={options}
        value={color}
        size="md"
        onSelect={(key: SwatchKey) => onColor(key as MarkupColor)}
        className="gap-0"
      />
      <FloatingToolbarSeparator />
      <FloatingToolbarButton className={TARGET} aria-label="Underline" aria-keyshortcuts="u" onClick={onUnderline}>
        <Underline aria-hidden />
      </FloatingToolbarButton>
      <FloatingToolbarButton size="sm" className="min-h-11" aria-keyshortcuts="n" onClick={onNote}>
        <StickyNote aria-hidden />
        Note
      </FloatingToolbarButton>
      {canCard ? (
        <FloatingToolbarButton
          size="sm"
          className="min-h-11"
          disabled={!!cardDisabledReason}
          title={cardDisabledReason}
          aria-label={cardKindName ? `Make a card: ${cardKindName}` : 'Make a card'}
          onClick={onCard}
        >
          <Layers aria-hidden />
          Card
        </FloatingToolbarButton>
      ) : null}
      <FloatingToolbarButton className={TARGET} aria-label="Copy text" onClick={onCopy}>
        <Copy aria-hidden />
      </FloatingToolbarButton>
    </FloatingToolbar>
  )
}
