import { Alert, Button, Checkbox, Label, NumberStepper, Sparkles, Textarea } from '@artha/design-system'
import { type ReactNode, useId } from 'react'

import { AI_SOURCES, type AiOverview, type AiSource } from '../lib/schemas'
import { quotaText, SOURCE_LABEL } from '../lib/suggestions'

export interface RequestFormProps {
  overview: AiOverview
  /** The chapter chooser (the container passes it in, so this stays props only). */
  chapterField: ReactNode
  sources: AiSource[]
  onSources: (sources: AiSource[]) => void
  pasted: string
  onPasted: (text: string) => void
  count: number
  onCount: (count: number) => void
  /** Why the button is not ready, shown as plain text under it; null when it is ready. */
  problem: string | null
  pending: boolean
  offline: boolean
  error: string | null
  onSubmit: () => void
}

export function SuggestRequestForm(p: RequestFormProps) {
  const id = useId()
  const pastedOn = p.sources.includes('pasted')
  const toggle = (s: AiSource, on: boolean) => p.onSources(on ? [...p.sources, s] : p.sources.filter((x) => x !== s))
  const max = Math.max(p.overview.limits.max_count, p.overview.limits.min_count)
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        if (!p.problem && !p.pending && !p.offline) p.onSubmit()
      }}
      aria-label="Ask for card suggestions"
    >
      {p.chapterField}

      <fieldset className="space-y-2">
        <legend className="text-[13px] font-semibold">Where should the cards come from?</legend>
        {AI_SOURCES.map((s) => {
          const connected = p.overview.sources.includes(s)
          return (
            <div key={s} className="flex items-start gap-3">
              <Checkbox
                id={`${id}-${s}`}
                checked={p.sources.includes(s)}
                disabled={!connected}
                onCheckedChange={(v) => toggle(s, v === true)}
                aria-describedby={`${id}-${s}-help`}
              />
              <div>
                <Label htmlFor={`${id}-${s}`}>{SOURCE_LABEL[s].title}</Label>
                <p id={`${id}-${s}-help`} className="text-xs text-muted-foreground">
                  {connected ? SOURCE_LABEL[s].help : 'Not available yet.'}
                </p>
              </div>
            </div>
          )
        })}
      </fieldset>

      {pastedOn ? (
        <div className="space-y-2">
          <Label htmlFor={`${id}-text`}>Text to make cards from</Label>
          <Textarea
            id={`${id}-text`}
            value={p.pasted}
            maxLength={p.overview.limits.max_pasted_chars}
            rows={6}
            onChange={(e) => p.onPasted(e.target.value)}
            aria-describedby={`${id}-text-count`}
          />
          <p id={`${id}-text-count`} className="text-xs text-muted-foreground">
            {p.pasted.length} of {p.overview.limits.max_pasted_chars} characters
          </p>
        </div>
      ) : null}

      <div className="space-y-2">
        <p className="text-[13px] font-semibold">How many cards?</p>
        <NumberStepper
          label="Number of cards"
          value={p.count}
          min={p.overview.limits.min_count}
          max={max}
          onChange={p.onCount}
        />
      </div>

      <p className="text-xs text-muted-foreground">{quotaText(p.overview.quota)}</p>

      {p.error ? <Alert variant="error">{p.error}</Alert> : null}
      {p.offline ? <Alert>You are offline. Connect to ask for suggestions.</Alert> : null}

      <div className="space-y-2">
        <Button type="submit" disabled={p.pending || p.offline || p.problem !== null} aria-describedby={`${id}-why`}>
          <Sparkles aria-hidden /> {p.pending ? 'Sending…' : 'Suggest cards'}
        </Button>
        <p id={`${id}-why`} className="text-xs text-muted-foreground">
          {p.problem ?? 'Nothing becomes a card until you accept it.'}
        </p>
      </div>
    </form>
  )
}
