import { Alert, Button, List, SyncChip } from '@artha/design-system'

import { ToolOptions, ToolPill } from '../components/annotations/ToolPill'
import { inkOptions } from '../lib/annotation-legend'
import { type ReaderTool } from '../lib/reader-schema'
import { useUiScope } from './annotation-scope'

/** The tool pill and the options of the active tool, in the reader's bottom bar. */
export function MarksTools() {
  const ui = useUiScope()
  if (!ui) return null
  const { tool, settings, marks } = ui
  return (
    <div data-slot="marks-tools">
      {marks.notice === 'blocked' ? (
        <div className="mx-auto w-full max-w-3xl px-3 pt-1">
          <Alert variant="error">
            <span className="flex flex-wrap items-center gap-2">
              <span>This PDF has reached its limit of marks.</span>
              <Button size="sm" variant="outline" className="min-h-11" onClick={() => ui.setListOpen(true)}>
                Free up room
              </Button>
            </span>
          </Alert>
        </div>
      ) : null}
      <ToolPill tool={tool} onToolChange={ui.setTool} />
      {tool ? (
        <ToolOptions
          tool={tool as ReaderTool}
          markupOptions={settings.options}
          markupColor={ui.markupColor}
          onMarkupColor={(key) => ui.setMarkupColor(key as typeof ui.markupColor)}
          inkOptions={inkOptions()}
          inkColor={ui.inkColor}
          onInkColor={(key) => ui.setInkColor(key as typeof ui.inkColor)}
          penWidth={ui.penWidth}
          onPenWidth={ui.setPenWidth}
          canUndo={ui.ink.canUndo}
          canRedo={ui.ink.canRedo}
          onUndo={ui.ink.undo}
          onRedo={ui.ink.redo}
          fingerDraws={settings.fingerDraws}
        />
      ) : null}
    </div>
  )
}

/** "Saved", "Saving…", "Offline: saved on this device, 3 waiting" or "1 needs your attention" (a live region). */
export function MarksSyncChip() {
  const ui = useUiScope()
  if (!ui) return null
  const { sync } = ui.marks
  return (
    <SyncChip
      state={sync.state}
      count={sync.count}
      onPress={sync.state === 'attention' ? () => ui.setConflictOpen(true) : undefined}
    />
  )
}

/** "12 marks": opens the list. */
export function MarksCountButton() {
  const ui = useUiScope()
  if (!ui) return null
  const n = ui.marks.marks.length
  return (
    <Button
      variant="ghost"
      size="sm"
      className="min-h-11 tabular-nums"
      onClick={() => ui.setListOpen(!ui.listOpen)}
      aria-expanded={ui.listOpen}
      aria-label={`${n} ${n === 1 ? 'mark' : 'marks'}. Open the list`}
    >
      {n} {n === 1 ? 'mark' : 'marks'}
    </Button>
  )
}

/** The top bar's button for the list of marks. */
export function MarksListButton() {
  const ui = useUiScope()
  if (!ui) return null
  return (
    <Button
      variant="ghost"
      size="icon"
      className="size-11"
      onClick={() => ui.setListOpen(!ui.listOpen)}
      aria-label="Marks in this PDF"
      aria-pressed={ui.listOpen}
    >
      <List aria-hidden />
    </Button>
  )
}
