import {
  Button,
  Layers,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  type SwatchKey,
  type SwatchOption,
  SwatchPicker,
  Textarea,
  Trash2,
} from '@artha/design-system'
import { type ReactNode, type RefObject } from 'react'

import type { ColorKey, MarkKind } from '../../lib/annotation-types'
import { MAX_COMMENT } from '../../lib/mark-drafts'

export interface AnnotationEditSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  kind: MarkKind
  /** "Highlight, page 14": the first words of the row. */
  heading: string
  /** The quoted text of a highlight or underline, shown as context (never editable). */
  quote?: string
  color: ColorKey | null
  /** Colours this kind can have: the student's legend for markup and notes, pens for drawings and text boxes. */
  colorOptions: SwatchOption[]
  colorLabel: string
  onColor: (key: ColorKey) => void
  comment: string
  onCommentChange: (text: string) => void
  commentRef?: RefObject<HTMLTextAreaElement | null>
  /** The tag editor (a container passes `TagEditor` with the account's tags). */
  tags: ReactNode
  /** The chapter row: the chip and the button that opens the chapter picker. */
  chapter: ReactNode
  canCard: boolean
  /** Why "Make card" cannot be used right now (offline). */
  cardDisabledReason?: string
  hasCard: boolean
  onCard: () => void
  onDelete: () => void
}

/** What the comment field is called for each kind (a bookmark has a title, a text box has its text). */
export const COMMENT_FIELD: Record<MarkKind, { label: string; placeholder: string }> = {
  highlight: { label: 'Comment', placeholder: 'Why this matters, a doubt, an example' },
  underline: { label: 'Comment', placeholder: 'Why this matters, a doubt, an example' },
  area: { label: 'Comment', placeholder: 'What is in this figure' },
  ink: { label: 'Comment', placeholder: 'What this drawing shows' },
  sticky: { label: 'Note', placeholder: 'Write your note' },
  textbox: { label: 'Text', placeholder: 'Type on the page' },
  bookmark: { label: 'Title', placeholder: 'Name this place' },
}

const CARD_KINDS: ReadonlySet<MarkKind> = new Set(['highlight', 'underline', 'sticky'])

/**
 * Everything about one mark in one sheet: the colour by name, the comment, tags, chapter, "Make card" and Delete (which
 * can be undone for 10 seconds). Changes save as the student makes them, so there is no Save button; closing keeps them.
 */
export function AnnotationEditSheet({
  open,
  onOpenChange,
  kind,
  heading,
  quote,
  color,
  colorOptions,
  colorLabel,
  onColor,
  comment,
  onCommentChange,
  commentRef,
  tags,
  chapter,
  canCard,
  cardDisabledReason,
  hasCard,
  onCard,
  onDelete,
}: AnnotationEditSheetProps) {
  const field = COMMENT_FIELD[kind]
  const showCard = canCard && CARD_KINDS.has(kind)
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        onOpenAutoFocus={(e) => {
          if (commentRef?.current) {
            e.preventDefault()
            commentRef.current.focus()
          }
        }}
        className="max-h-[92dvh] overflow-y-auto sm:mx-auto sm:max-w-xl"
      >
        <SheetHeader>
          <SheetTitle>{heading}</SheetTitle>
          <SheetDescription>Changes save as you make them.</SheetDescription>
        </SheetHeader>
        <div className="space-y-5">
          {quote ? (
            <blockquote className="line-clamp-4 border-l-4 border-border pl-3 text-sm text-muted-foreground">
              {quote}
            </blockquote>
          ) : null}
          {colorOptions.length > 0 ? (
            <div className="space-y-2">
              <p id="mark-colour-label" className="text-sm font-medium">
                {colorLabel}
              </p>
              <SwatchPicker
                label={colorLabel}
                options={colorOptions}
                showNames
                value={(color as SwatchKey | null) ?? null}
                onValueChange={(key) => onColor(key)}
                className="gap-2"
              />
            </div>
          ) : null}
          <div className="grid gap-2">
            <label htmlFor="mark-comment" className="text-sm font-medium">
              {field.label}
            </label>
            <Textarea
              id="mark-comment"
              ref={commentRef as RefObject<HTMLTextAreaElement>}
              value={comment}
              maxLength={MAX_COMMENT}
              rows={kind === 'bookmark' ? 1 : 4}
              placeholder={field.placeholder}
              onChange={(e) => onCommentChange(e.target.value)}
            />
            <p className="text-xs text-muted-foreground tabular-nums">
              {comment.length} / {MAX_COMMENT}
            </p>
          </div>
          <div className="space-y-2">
            <p className="text-sm font-medium">Tags</p>
            {tags}
          </div>
          <div className="space-y-2">
            <p className="text-sm font-medium">Chapter</p>
            {chapter}
          </div>
        </div>
        <SheetFooter className="mt-6 sm:justify-between">
          <Button variant="danger" className="min-h-11" onClick={onDelete}>
            <Trash2 aria-hidden /> Delete
          </Button>
          {showCard ? (
            <Button
              variant="outline"
              className="min-h-11"
              onClick={onCard}
              disabled={!!cardDisabledReason}
              title={cardDisabledReason}
            >
              <Layers aria-hidden /> {hasCard ? 'Make another card' : 'Make card'}
            </Button>
          ) : null}
        </SheetFooter>
        {cardDisabledReason && showCard ? (
          <p className="mt-2 text-xs text-muted-foreground">{cardDisabledReason}</p>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
