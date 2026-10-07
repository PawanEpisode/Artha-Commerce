import { Button, Popover, PopoverContent, PopoverTrigger, Slider, Undo2 } from '@artha/design-system'
import { type FormEvent, type ReactNode, useEffect, useState } from 'react'

export interface PageScrubberProps {
  page: number
  pageCount: number
  onGo: (page: number) => void
  /** The page the student jumped from (outline, scrubber, search): a Back chip for it is shown. */
  backTo?: number | null
  onBack?: () => void
  /** Left and right of the page indicator: the sync chip and the marks count of the annotation layer. */
  leftSlot?: ReactNode
  rightSlot?: ReactNode
  disabled?: boolean
}

const ANNOUNCE_DELAY_MS = 500

/**
 * "p. 142 / 328", a slider over all pages, a "go to page" field and the Back chip that follows a jump. The page number is
 * announced politely after scrolling settles (not on every page that scrolls past).
 */
export function PageScrubber({
  page,
  pageCount,
  onGo,
  backTo,
  onBack,
  leftSlot,
  rightSlot,
  disabled,
}: PageScrubberProps) {
  const [drag, setDrag] = useState<number | null>(null)
  const [announced, setAnnounced] = useState('')
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')

  useEffect(() => {
    const t = setTimeout(() => setAnnounced(`Page ${page} of ${pageCount}`), ANNOUNCE_DELAY_MS)
    return () => clearTimeout(t)
  }, [page, pageCount])

  const shown = drag ?? page
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const n = Number.parseInt(text, 10)
    if (Number.isFinite(n) && n >= 1) {
      onGo(Math.min(n, pageCount))
      setOpen(false)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-0.5 px-3 pt-1 pb-2">
      <div className="flex min-h-11 items-center justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-center">{leftSlot}</div>
        <Popover
          open={open}
          onOpenChange={(next) => {
            setOpen(next)
            if (next) setText(String(page))
          }}
        >
          <PopoverTrigger asChild>
            <Button
              variant="ghost"
              className="min-w-28 tabular-nums"
              disabled={disabled}
              aria-label={`Page ${shown} of ${pageCount}. Go to page`}
            >
              p. {shown} / {pageCount}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-60">
            <form onSubmit={submit} className="grid gap-2">
              <label htmlFor="reader-goto" className="text-sm font-medium">
                Go to page
              </label>
              <div className="flex gap-2">
                <input
                  id="reader-goto"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={pageCount}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  className="h-11 min-w-0 flex-1 rounded-lg border border-input bg-card px-3 text-base tabular-nums outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
                />
                <Button type="submit">Go</Button>
              </div>
              <p className="text-xs text-muted-foreground">1 to {pageCount}</p>
            </form>
          </PopoverContent>
        </Popover>
        <div className="flex min-w-0 flex-1 items-center justify-end gap-1">
          {backTo ? (
            <Button variant="outline" size="sm" onClick={onBack} className="min-h-11">
              <Undo2 aria-hidden />
              Back to p. {backTo}
            </Button>
          ) : null}
          {rightSlot}
        </div>
      </div>
      {pageCount > 1 ? (
        <Slider
          label="Page"
          min={1}
          max={pageCount}
          step={1}
          value={shown}
          disabled={disabled}
          onValueChange={setDrag}
          onValueCommit={([v]: number[]) => {
            setDrag(null)
            if (v !== undefined) onGo(v)
          }}
        />
      ) : null}
      <p className="sr-only" role="status" aria-live="polite">
        {announced}
      </p>
    </div>
  )
}
