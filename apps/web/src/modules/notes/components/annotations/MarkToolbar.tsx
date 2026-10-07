import {
  FloatingToolbar,
  type FloatingToolbarAnchor,
  FloatingToolbarButton,
  FloatingToolbarSeparator,
  Layers,
  Pencil,
  type SwatchKey,
  type SwatchOption,
  SwatchPicker,
  Trash2,
} from '@artha/design-system'
import type { RefObject } from 'react'

import type { ColorKey } from '../../lib/annotation-types'

export interface MarkToolbarProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  anchor: FloatingToolbarAnchor
  scrollContainer?: Element | null
  returnFocusRef?: RefObject<HTMLElement | null>
  /** The colours this kind can have (legend for markup and notes, pens for drawings and text boxes). */
  options: SwatchOption[]
  color: ColorKey | null
  canCard: boolean
  hasCard: boolean
  onColor: (key: ColorKey) => void
  onEdit: () => void
  onCard: () => void
  onDelete: () => void
}

/** The bar over a selected mark: change its colour, open the edit sheet, make a card, delete (with Undo). */
export function MarkToolbar({
  open,
  onOpenChange,
  anchor,
  scrollContainer,
  returnFocusRef,
  options,
  color,
  canCard,
  hasCard,
  onColor,
  onEdit,
  onCard,
  onDelete,
}: MarkToolbarProps) {
  return (
    <FloatingToolbar
      open={open}
      onOpenChange={onOpenChange}
      anchor={anchor}
      scrollContainer={scrollContainer}
      returnFocusRef={returnFocusRef}
      label="Selected mark"
      side="bottom"
    >
      {options.length > 0 ? (
        <>
          <SwatchPicker
            label="Colour"
            options={options}
            value={color}
            size="md"
            onSelect={(key: SwatchKey) => onColor(key)}
            className="gap-0"
          />
          <FloatingToolbarSeparator />
        </>
      ) : null}
      <FloatingToolbarButton size="sm" className="min-h-11" onClick={onEdit}>
        <Pencil aria-hidden />
        Edit
      </FloatingToolbarButton>
      {canCard && !hasCard ? (
        <FloatingToolbarButton size="sm" className="min-h-11" onClick={onCard}>
          <Layers aria-hidden />
          Card
        </FloatingToolbarButton>
      ) : null}
      <FloatingToolbarButton className="size-11 min-h-11 min-w-11" aria-label="Delete mark" onClick={onDelete}>
        <Trash2 aria-hidden />
      </FloatingToolbarButton>
    </FloatingToolbar>
  )
}
