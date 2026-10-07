import type { ColorKey, InkColor, MarkupColor } from '../../lib/annotation-types'

/**
 * Tailwind sees class names only when they are written out in full, so every colour has its row here. Fills use the
 * page-tone alpha (`--mark-fill-alpha`: dimmer on a night page); edges and pens are full strength and carry the 3:1.
 */
export const HL_FILL: Record<MarkupColor, string> = {
  y: 'bg-highlight-yellow/(--mark-fill-alpha)',
  g: 'bg-highlight-green/(--mark-fill-alpha)',
  b: 'bg-highlight-blue/(--mark-fill-alpha)',
  p: 'bg-highlight-pink/(--mark-fill-alpha)',
  o: 'bg-highlight-orange/(--mark-fill-alpha)',
}
export const HL_SOLID: Record<MarkupColor, string> = {
  y: 'bg-highlight-yellow',
  g: 'bg-highlight-green',
  b: 'bg-highlight-blue',
  p: 'bg-highlight-pink',
  o: 'bg-highlight-orange',
}
export const HL_BORDER: Record<MarkupColor, string> = {
  y: 'border-highlight-yellow-edge',
  g: 'border-highlight-green-edge',
  b: 'border-highlight-blue-edge',
  p: 'border-highlight-pink-edge',
  o: 'border-highlight-orange-edge',
}
export const HL_EDGE_TEXT: Record<MarkupColor, string> = {
  y: 'text-highlight-yellow-edge',
  g: 'text-highlight-green-edge',
  b: 'text-highlight-blue-edge',
  p: 'text-highlight-pink-edge',
  o: 'text-highlight-orange-edge',
}
export const INK_STROKE: Record<InkColor, string> = {
  i1: 'stroke-ink-1',
  i2: 'stroke-ink-2',
  i3: 'stroke-ink-3',
  i4: 'stroke-ink-4',
  i5: 'stroke-ink-5',
}
export const INK_TEXT: Record<InkColor, string> = {
  i1: 'text-ink-1',
  i2: 'text-ink-2',
  i3: 'text-ink-3',
  i4: 'text-ink-4',
  i5: 'text-ink-5',
}
export const INK_BORDER: Record<InkColor, string> = {
  i1: 'border-ink-1',
  i2: 'border-ink-2',
  i3: 'border-ink-3',
  i4: 'border-ink-4',
  i5: 'border-ink-5',
}

export const markupOf = (key: ColorKey | null): MarkupColor =>
  key && !key.startsWith('i') ? (key as MarkupColor) : 'y'
export const inkOf = (key: ColorKey | null): InkColor => (key?.startsWith('i') ? (key as InkColor) : 'i1')

/** A small round chip in the mark's colour with its shape inside (the list row's marker). Same classes as the swatches. */
export const CHIP: Record<ColorKey, string> = {
  y: 'border-2 border-highlight-yellow-edge bg-highlight-yellow text-swatch-marker',
  g: 'border-2 border-highlight-green-edge bg-highlight-green text-swatch-marker',
  b: 'border-2 border-highlight-blue-edge bg-highlight-blue text-swatch-marker',
  p: 'border-2 border-highlight-pink-edge bg-highlight-pink text-swatch-marker',
  o: 'border-2 border-highlight-orange-edge bg-highlight-orange text-swatch-marker',
  i1: 'border-2 border-ink-1 bg-ink-1 text-swatch-marker-inverse',
  i2: 'border-2 border-ink-2 bg-ink-2 text-swatch-marker-inverse',
  i3: 'border-2 border-ink-3 bg-ink-3 text-swatch-marker-inverse',
  i4: 'border-2 border-ink-4 bg-ink-4 text-swatch-marker-inverse',
  i5: 'border-2 border-ink-5 bg-ink-5 text-swatch-marker-inverse',
}
