import {
  Badge,
  BoxSelect,
  Highlighter,
  Layers,
  StickyNote,
  TableCell,
  TableRow,
  Tag,
  Type,
  Underline,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { isUnfiled, linkLabel, shortLinkLabel } from '../../lib/chapter-link'
import { formatDate } from '../../lib/format'
import type { HighlightRow as Row, MarkKind } from '../../lib/library-types'
import { markOpenedFrom } from '../../lib/opened-from'

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

/** One mark in the aggregated table: kind icon and text, colour name, document and page, chapter, tags, card badge. Opens the PDF at the mark. */
export function HighlightRow({ row, colorName, documentTitle, showLocation = true }: HighlightRowProps) {
  const kind = KIND[row.kind] ?? KIND.highlight
  const Icon = kind.icon
  const text = row.quote_exact?.trim() || row.comment.trim() || `${kind.label} on page ${row.page}`
  return (
    <TableRow data-slot="highlight-row">
      <TableCell className="min-w-48 py-2 whitespace-normal">
        <div className="flex items-start gap-2">
          <Icon aria-hidden className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
          <div className="min-w-0 space-y-0.5">
            <p className="line-clamp-2 break-words">
              <Link
                to="/app/notes/pdf/$docId"
                params={{ docId: row.document_id }}
                search={{ page: row.page, ann: row.id }}
                onClick={() => markOpenedFrom('aggregate')}
                className="font-medium underline-offset-4 outline-none hover:underline focus-visible:underline focus-visible:ring-2 focus-visible:ring-ring/50"
              >
                <span className="sr-only">{kind.label}: </span>
                {text}
              </Link>
            </p>
            {row.quote_exact && row.comment.trim() ? (
              <p className="line-clamp-1 text-xs break-words text-muted-foreground">{row.comment}</p>
            ) : null}
            <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
              {row.color ? (
                <span className="inline-flex items-center gap-1.5 font-medium text-foreground">
                  <ColorDot color={row.color} />
                  {colorName ?? 'Colour'}
                </span>
              ) : null}
              <span className="min-w-0 break-words">
                {documentTitle ? `${documentTitle} · ` : ''}page {row.page}
              </span>
              {row.recall_card_id ? (
                <Badge variant="accent">
                  <Layers aria-hidden />
                  Card
                </Badge>
              ) : null}
            </p>
          </div>
        </div>
      </TableCell>
      {showLocation ? (
        <TableCell className="max-w-56">
          <div className="flex min-w-0 flex-wrap items-center gap-1">
            {!isUnfiled(row.link) ? (
              <Badge variant="outline" className="max-w-full min-w-0" title={linkLabel(row.link)}>
                <span className="truncate">{shortLinkLabel(row.link)}</span>
              </Badge>
            ) : null}
            {row.link.moved_or_removed ? (
              <Badge variant="outline" className="max-w-full min-w-0">
                <span className="truncate">Chapter moved or removed</span>
              </Badge>
            ) : null}
          </div>
        </TableCell>
      ) : null}
      <TableCell className="hidden md:table-cell">
        <div className="flex max-w-56 min-w-0 flex-wrap items-center gap-1">
          {row.tags.map((tag) => (
            <Badge key={tag.id} variant="outline" className="max-w-full min-w-0" title={tag.name}>
              <Tag aria-hidden className="shrink-0" />
              <span className="truncate">{tag.name}</span>
            </Badge>
          ))}
        </div>
      </TableCell>
      <TableCell className="text-right text-xs whitespace-nowrap text-muted-foreground tabular-nums">
        <time dateTime={row.updated_at}>{formatDate(row.updated_at)}</time>
      </TableCell>
      <TableCell className="w-px" />
    </TableRow>
  )
}
