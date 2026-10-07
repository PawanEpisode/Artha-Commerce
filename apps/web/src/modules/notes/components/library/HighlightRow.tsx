import { Badge, BoxSelect, Card, Highlighter, Layers, StickyNote, Tag, Type, Underline } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { isUnfiled, linkLabel } from '../../lib/chapter-link'
import type { HighlightRow as Row, MarkKind } from '../../lib/library-types'

const KIND: Record<MarkKind, { icon: typeof Highlighter; label: string }> = {
  highlight: { icon: Highlighter, label: 'Highlight' },
  underline: { icon: Underline, label: 'Underline' },
  area: { icon: BoxSelect, label: 'Area highlight' },
  sticky: { icon: StickyNote, label: 'Sticky note' },
  textbox: { icon: Type, label: 'Text box' },
  ink: { icon: Highlighter, label: 'Drawing' },
  bookmark: { icon: Highlighter, label: 'Bookmark' },
}

/** Fill and edge per legend key. The colour's NAME is always written next to it, so colour is never the only signal. */
const DOT: Record<string, string> = {
  y: 'border-highlight-yellow-edge bg-highlight-yellow',
  g: 'border-highlight-green-edge bg-highlight-green',
  b: 'border-highlight-blue-edge bg-highlight-blue',
  p: 'border-highlight-pink-edge bg-highlight-pink',
  o: 'border-highlight-orange-edge bg-highlight-orange',
}

/** The colour swatch. Always sits next to the colour's name. */
export function ColorDot({ color }: { color: string }) {
  return <span aria-hidden className={`size-3 rounded-full border ${DOT[color] ?? 'border-border bg-muted'}`} />
}

interface HighlightRowProps {
  row: Row
  /** The student's name for the colour (their legend), "Formula". */
  colorName?: string
  documentTitle?: string
  /** Hide the chapter line when the page already says it. */
  showLocation?: boolean
}

/** One mark in the aggregated views: kind icon and text, colour name, document and page, chapter, tags, card badge. Opens the PDF at the mark. */
export function HighlightRow({ row, colorName, documentTitle, showLocation = true }: HighlightRowProps) {
  const kind = KIND[row.kind] ?? KIND.highlight
  const Icon = kind.icon
  const text = row.quote_exact?.trim() || row.comment.trim() || `${kind.label} on page ${row.page}`
  return (
    <Card data-slot="highlight-row" className="space-y-2 p-4">
      <div className="flex items-start gap-3">
        <span aria-hidden className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-muted">
          <Icon className="size-4" />
        </span>
        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="line-clamp-3 text-base leading-snug break-words">
            <Link
              to="/app/notes/pdf/$docId"
              params={{ docId: row.document_id }}
              search={{ page: row.page, ann: row.id }}
              className="underline-offset-4 outline-none hover:underline focus-visible:underline focus-visible:ring-[3px] focus-visible:ring-ring/40"
            >
              <span className="sr-only">{kind.label}: </span>
              {text}
            </Link>
          </p>
          {row.quote_exact && row.comment.trim() ? (
            <p className="line-clamp-2 text-sm break-words text-muted-foreground">{row.comment}</p>
          ) : null}
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
            {row.color ? (
              <span className="inline-flex items-center gap-1.5 font-medium text-foreground">
                <ColorDot color={row.color} />
                {colorName ?? 'Colour'}
              </span>
            ) : null}
            <span className="min-w-0 break-words">
              {documentTitle ? `${documentTitle} · ` : ''}page {row.page}
            </span>
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        {showLocation && !isUnfiled(row.link) ? <Badge variant="outline">{linkLabel(row.link)}</Badge> : null}
        {row.link.moved_or_removed ? <Badge variant="outline">Chapter moved or removed</Badge> : null}
        {row.tags.map((tag) => (
          <Badge key={tag.id} variant="outline">
            <Tag aria-hidden className="size-3" />
            {tag.name}
          </Badge>
        ))}
        {row.recall_card_id ? (
          <Badge variant="accent">
            <Layers aria-hidden className="size-3" />
            Card
          </Badge>
        ) : null}
      </div>
    </Card>
  )
}
