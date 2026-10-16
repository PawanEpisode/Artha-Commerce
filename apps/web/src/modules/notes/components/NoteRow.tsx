import { Badge, Button, CloudOff, Pin, PinOff, TableCell, TableRow, Tag, Trash2 } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { isUnfiled, linkLabel, shortLinkLabel } from '../lib/chapter-link'
import { relativeTime } from '../lib/format'
import type { NoteSummary } from '../lib/types'

interface NoteRowProps {
  note: NoteSummary
  /** Hide the "filed under" column when the page already says it (a chapter page). */
  showLocation?: boolean
  onPin?: (pinned: boolean) => void
  onTrash?: () => void
}

/** The link style of a row title. */
export const NOTE_LINK_CLASS =
  'underline-offset-4 outline-none hover:underline focus-visible:underline focus-visible:ring-2 focus-visible:ring-ring/50'

/** One note as a table row: title link with a one line snippet, where it is filed, tags, updated, quick actions. */
export function NoteRow({ note, showLocation = true, onPin, onTrash }: NoteRowProps) {
  const title = note.title.trim() || 'Untitled note'
  const filed = !isUnfiled(note.link)
  return (
    <TableRow>
      <TableCell className="min-w-48 py-2 whitespace-normal">
        <Link
          to="/app/notes/n/$noteId"
          params={{ noteId: note.id }}
          className={`block min-w-0 font-medium break-words ${NOTE_LINK_CLASS}`}
        >
          {note.pinned ? <Pin aria-label="Pinned" className="mr-1 inline size-3.5 align-[-2px]" /> : null}
          {title}
        </Link>
        {note.snippet ? <p className="line-clamp-1 text-xs break-words text-muted-foreground">{note.snippet}</p> : null}
        {note.offline_copy ? (
          <Badge variant="accent" className="mt-1">
            <CloudOff aria-hidden />
            Offline copy
          </Badge>
        ) : null}
      </TableCell>
      {showLocation ? (
        <TableCell className="max-w-56">
          <div className="flex min-w-0 flex-wrap items-center gap-1">
            <Badge
              variant={filed ? 'outline' : 'highlight'}
              className="max-w-full min-w-0"
              title={filed ? linkLabel(note.link) : undefined}
            >
              <span className="truncate">{filed ? shortLinkLabel(note.link) : 'Unfiled'}</span>
            </Badge>
            {note.link.moved_or_removed ? (
              <Badge variant="outline" className="max-w-full min-w-0">
                <span className="truncate">Chapter moved or removed</span>
              </Badge>
            ) : null}
          </div>
        </TableCell>
      ) : null}
      <TableCell className="hidden md:table-cell">
        <div className="flex max-w-56 min-w-0 flex-wrap items-center gap-1">
          {note.tags.map((tag) => (
            <Badge key={tag.id} variant="outline" className="max-w-full min-w-0" title={tag.name}>
              <Tag aria-hidden className="shrink-0" />
              <span className="truncate">{tag.name}</span>
            </Badge>
          ))}
        </div>
      </TableCell>
      <TableCell className="text-right text-xs whitespace-nowrap text-muted-foreground tabular-nums">
        <time dateTime={note.updated_at}>{relativeTime(note.updated_at)}</time>
      </TableCell>
      <TableCell className="w-px text-right whitespace-nowrap">
        {onPin ? (
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={note.pinned ? `Unpin ${title}` : `Pin ${title}`}
            aria-pressed={note.pinned}
            onClick={() => onPin(!note.pinned)}
          >
            {note.pinned ? <PinOff aria-hidden /> : <Pin aria-hidden />}
          </Button>
        ) : null}
        {onTrash ? (
          <Button variant="ghost" size="icon-sm" aria-label={`Move ${title} to Trash`} onClick={onTrash}>
            <Trash2 aria-hidden />
          </Button>
        ) : null}
      </TableCell>
    </TableRow>
  )
}

/** Columns in a notes table: title, filed under (optional), tags, updated, actions. */
export function noteColumnCount(showLocation: boolean) {
  return showLocation ? 5 : 4
}
