import { Badge, Button, Card, CloudOff, Pin, PinOff, Tag, Trash2 } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { isUnfiled, linkLabel } from '../lib/chapter-link'
import { relativeTime } from '../lib/format'
import type { NoteSummary } from '../lib/types'

interface NoteCardProps {
  note: NoteSummary
  /** Hide the "where it is filed" line when the page already says it (a chapter page). */
  showLocation?: boolean
  onPin?: (pinned: boolean) => void
  onTrash?: () => void
}

/** One note in a list: title, a two line snippet, where it is filed, tags and the quick actions. */
export function NoteCard({ note, showLocation = true, onPin, onTrash }: NoteCardProps) {
  const title = note.title.trim() || 'Untitled note'
  return (
    <Card className="flex items-start gap-2 p-4">
      <div className="min-w-0 flex-1 space-y-2">
        <h3 className="font-display text-lg leading-snug font-bold break-words">
          <Link
            to="/app/notes/n/$noteId"
            params={{ noteId: note.id }}
            className="underline-offset-4 outline-none hover:underline focus-visible:underline focus-visible:ring-[3px] focus-visible:ring-ring/40"
          >
            {note.pinned ? <Pin aria-label="Pinned" className="mr-1.5 inline size-4 align-[-2px]" /> : null}
            {title}
          </Link>
        </h3>
        {note.snippet ? <p className="line-clamp-2 text-sm break-words text-muted-foreground">{note.snippet}</p> : null}
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          {showLocation ? (
            <Badge variant={isUnfiled(note.link) ? 'highlight' : 'outline'}>{linkLabel(note.link)}</Badge>
          ) : null}
          {note.link.moved_or_removed ? <Badge variant="outline">Chapter moved or removed</Badge> : null}
          {note.tags.map((tag) => (
            <Badge key={tag.id} variant="outline">
              <Tag aria-hidden className="size-3" />
              {tag.name}
            </Badge>
          ))}
          {note.offline_copy ? (
            <Badge variant="accent">
              <CloudOff aria-hidden className="size-3" />
              Offline copy
            </Badge>
          ) : null}
          <span className="text-muted-foreground">
            <time dateTime={note.updated_at}>{relativeTime(note.updated_at)}</time>
          </span>
        </div>
      </div>
      <div className="flex shrink-0 flex-col gap-1 sm:flex-row">
        {onPin ? (
          <Button
            variant="ghost"
            size="icon"
            className="size-11"
            aria-label={note.pinned ? `Unpin ${title}` : `Pin ${title}`}
            aria-pressed={note.pinned}
            onClick={() => onPin(!note.pinned)}
          >
            {note.pinned ? <PinOff aria-hidden /> : <Pin aria-hidden />}
          </Button>
        ) : null}
        {onTrash ? (
          <Button
            variant="ghost"
            size="icon"
            className="size-11"
            aria-label={`Move ${title} to Trash`}
            onClick={onTrash}
          >
            <Trash2 aria-hidden />
          </Button>
        ) : null}
      </div>
    </Card>
  )
}
