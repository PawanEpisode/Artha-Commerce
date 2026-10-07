import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@artha/design-system'

import type { OutlineNode } from '../../lib/document-types'

export interface OutlinePanelProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  outline: ReadonlyArray<OutlineNode>
  currentPage: number
  /** Jumps to the entry's page. The panel closes and the reader shows the Back chip. */
  onGo: (page: number) => void
}

/** The PDF's own bookmarks as a tree of buttons (every level expanded, so a screen reader and a keyboard reach all of it). */
export function OutlinePanel({ open, onOpenChange, outline, currentPage, onGo }: OutlinePanelProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex flex-col gap-3 overflow-hidden">
        <SheetHeader>
          <SheetTitle>Contents</SheetTitle>
          <SheetDescription>Jump to a section. You can come back to where you were.</SheetDescription>
        </SheetHeader>
        <nav aria-label="Document outline" className="-mx-2 min-h-0 flex-1 overflow-y-auto px-2">
          <Nodes nodes={outline} currentPage={currentPage} onGo={(p) => onGo(p)} depth={0} />
        </nav>
      </SheetContent>
    </Sheet>
  )
}

function Nodes({
  nodes,
  currentPage,
  onGo,
  depth,
}: {
  nodes: ReadonlyArray<OutlineNode>
  currentPage: number
  onGo: (page: number) => void
  depth: number
}) {
  return (
    <ul className={depth > 0 ? 'ml-3 border-l border-border pl-2' : undefined}>
      {nodes.map((node, i) => {
        const row = (
          <button
            type="button"
            disabled={node.page < 1}
            onClick={() => onGo(node.page)}
            aria-current={node.page === currentPage ? 'location' : undefined}
            className="flex min-h-11 w-full items-center justify-between gap-3 rounded-lg px-2 py-1 text-left text-sm outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40 disabled:text-muted-foreground disabled:hover:bg-transparent aria-[current=location]:bg-secondary aria-[current=location]:font-semibold"
          >
            <span className="min-w-0 break-words">{node.title}</span>
            {node.page > 0 ? (
              <span className="shrink-0 text-xs text-muted-foreground tabular-nums">p. {node.page}</span>
            ) : null}
          </button>
        )
        return (
          <li key={`${i}-${node.title}`}>
            {row}
            {node.children.length > 0 ? (
              <Nodes nodes={node.children} currentPage={currentPage} onGo={onGo} depth={depth + 1} />
            ) : null}
          </li>
        )
      })}
    </ul>
  )
}
