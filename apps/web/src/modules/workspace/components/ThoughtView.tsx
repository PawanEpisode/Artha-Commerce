import { Sparkles } from '@artha/design-system'

interface Props {
  body: string
  /** Who or what the line is credited to; null for lines we wrote ourselves. */
  attribution: string | null
}

/** The day's line, as plain readable text. Decoration is hidden from assistive technology; the words carry it all. */
export function ThoughtView({ body, attribution }: Props) {
  return (
    <figure className="flex items-start gap-2">
      <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
      <div className="min-w-0 space-y-1">
        <blockquote className="text-sm leading-relaxed [overflow-wrap:anywhere] text-foreground">{body}</blockquote>
        {attribution ? (
          <figcaption className="text-[13px] [overflow-wrap:anywhere] text-muted-foreground">{attribution}</figcaption>
        ) : null}
      </div>
    </figure>
  )
}
