import { Sparkles } from '@artha/design-system'

interface Props {
  body: string
  /** Who or what the line is credited to; null for lines we wrote ourselves. */
  attribution: string | null
}

/** The day's line, as plain readable text. Decoration is hidden from assistive technology; the words carry it all. */
export function ThoughtView({ body, attribution }: Props) {
  return (
    <figure className="flex items-start gap-3">
      <Sparkles className="mt-1 size-5 shrink-0 text-primary" aria-hidden />
      <div className="min-w-0 space-y-2">
        <blockquote className="text-base leading-relaxed [overflow-wrap:anywhere] text-foreground">{body}</blockquote>
        {attribution ? (
          <figcaption className="text-sm [overflow-wrap:anywhere] text-muted-foreground">{attribution}</figcaption>
        ) : null}
      </div>
    </figure>
  )
}
