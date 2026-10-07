import {
  BookmarkPlus,
  BoxSelect,
  Button,
  Eraser,
  Highlighter,
  MousePointer2,
  PenLine,
  Redo2,
  SegmentedControl,
  StickyNote,
  type SwatchKey,
  type SwatchOption,
  SwatchPicker,
  Type,
  Underline,
  Undo2,
} from '@artha/design-system'
import type { ReactNode } from 'react'

import type { PenWidth } from '../../lib/mark-drafts'
import type { ReaderTool } from '../../lib/reader-schema'

/** The tools in the pill. `select` is "no tool": reading, with the selection toolbar. */
export type PillValue = ReaderTool | 'select'

const TOOLS: ReadonlyArray<{ value: PillValue; label: string; icon: ReactNode }> = [
  { value: 'select', label: 'Select', icon: <MousePointer2 aria-hidden /> },
  { value: 'highlight', label: 'Highlight', icon: <Highlighter aria-hidden /> },
  { value: 'underline', label: 'Underline', icon: <Underline aria-hidden /> },
  { value: 'pen', label: 'Pen', icon: <PenLine aria-hidden /> },
  { value: 'text', label: 'Text box', icon: <Type aria-hidden /> },
  { value: 'sticky', label: 'Pin', icon: <StickyNote aria-hidden /> },
  { value: 'bookmark', label: 'Bookmark', icon: <BookmarkPlus aria-hidden /> },
  { value: 'area', label: 'Area', icon: <BoxSelect aria-hidden /> },
  { value: 'eraser', label: 'Eraser', icon: <Eraser aria-hidden /> },
]

export interface ToolPillProps {
  /** The active tool from the URL, or undefined while reading. */
  tool: ReaderTool | undefined
  onToolChange: (tool: ReaderTool | undefined) => void
}

/**
 * One active tool at a time. While reading it collapses to a single "Mark" button (PRD 7.2); tapping it opens the row
 * with Select first, so leaving a tool is one tap (or Escape). A radio group underneath: arrow keys move the choice and
 * the group is announced as "1 of 9", the active tool is shown by a raised surface and never by colour alone.
 */
export function ToolPill({ tool, onToolChange }: ToolPillProps) {
  if (!tool) {
    return (
      <div className="mx-auto flex w-full max-w-3xl justify-center px-3 pt-1">
        <Button
          variant="secondary"
          className="min-h-11"
          onClick={() => onToolChange('highlight')}
          aria-label="Mark: open the highlight, pen and note tools"
        >
          <Highlighter aria-hidden />
          Mark
        </Button>
      </div>
    )
  }
  return (
    <div className="mx-auto flex w-full max-w-3xl justify-center px-3 pt-1">
      <SegmentedControl<PillValue>
        label="Annotation tools"
        size="lg"
        iconOnlyOnMobile
        value={tool}
        onValueChange={(next) => onToolChange(next === 'select' ? undefined : next)}
        options={TOOLS}
        className="max-w-full"
      />
    </div>
  )
}

export interface ToolOptionsProps {
  tool: ReaderTool
  /** Colours of the highlighter, underline, area and pin (the student's legend names). */
  markupOptions: SwatchOption[]
  markupColor: SwatchKey
  onMarkupColor: (key: SwatchKey) => void
  /** Pen and text box colours. */
  inkOptions: SwatchOption[]
  inkColor: SwatchKey
  onInkColor: (key: SwatchKey) => void
  penWidth: PenWidth
  onPenWidth: (width: PenWidth) => void
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
  /** One finger draws (so two fingers scroll); otherwise a stylus draws and a finger scrolls. */
  fingerDraws: boolean
}

const WIDTHS: ReadonlyArray<{ value: PenWidth; label: string }> = [
  { value: 'thin', label: 'Thin' },
  { value: 'medium', label: 'Medium' },
  { value: 'thick', label: 'Thick' },
]

const HELP: Partial<Record<ReaderTool, string>> = {
  highlight: 'Select text to highlight it.',
  underline: 'Select text to underline it.',
  text: 'Tap the page to place a text box.',
  sticky: 'Tap the page to place a note.',
  bookmark: 'Tap the page to add a bookmark.',
  area: 'Drag a rectangle over a figure or a scanned page.',
  eraser: 'Tap a mark to delete it. Undo brings it back.',
}

/** What the active tool needs, above the pill: colours, pen width, undo and redo, and the pen banner. */
export function ToolOptions(props: ToolOptionsProps) {
  const { tool } = props
  if (tool === 'pen')
    return (
      <div data-slot="pen-options" className="mx-auto flex w-full max-w-3xl flex-col gap-1 px-3 pt-1">
        <p role="status" className="text-center text-xs font-medium text-muted-foreground">
          {props.fingerDraws
            ? 'Pen on. Scroll with two fingers.'
            : 'Pen on. Scroll with two fingers. A stylus or mouse draws; one finger scrolls.'}
        </p>
        <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1">
          <SwatchPicker
            label="Pen colour"
            options={props.inkOptions}
            value={props.inkColor}
            size="sm"
            onValueChange={props.onInkColor}
          />
          <SegmentedControl<PenWidth>
            label="Pen width"
            size="lg"
            value={props.penWidth}
            onValueChange={props.onPenWidth}
            options={WIDTHS}
          />
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="size-11"
              disabled={!props.canUndo}
              onClick={props.onUndo}
              aria-label="Undo last stroke"
            >
              <Undo2 aria-hidden />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-11"
              disabled={!props.canRedo}
              onClick={props.onRedo}
              aria-label="Redo stroke"
            >
              <Redo2 aria-hidden />
            </Button>
          </div>
        </div>
      </div>
    )
  const withColour = tool === 'highlight' || tool === 'underline' || tool === 'area' || tool === 'sticky'
  return (
    <div data-slot="tool-options" className="mx-auto flex w-full max-w-3xl flex-col items-center gap-1 px-3 pt-1">
      {withColour ? (
        <SwatchPicker
          label="Colour"
          options={props.markupOptions}
          value={props.markupColor}
          size="sm"
          onValueChange={props.onMarkupColor}
        />
      ) : null}
      {tool === 'text' ? (
        <SwatchPicker
          label="Text colour"
          options={props.inkOptions}
          value={props.inkColor}
          size="sm"
          onValueChange={props.onInkColor}
        />
      ) : null}
      <p role="status" className="text-center text-xs text-muted-foreground">
        {HELP[tool]}
      </p>
    </div>
  )
}
