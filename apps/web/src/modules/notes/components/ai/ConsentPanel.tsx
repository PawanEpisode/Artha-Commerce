import { Alert, Button, Card, Checkbox, LoaderCircle, ShieldCheck } from '@artha/design-system'
import { useState } from 'react'

import type { AiConsentText } from '../../lib/ai-types'

interface ConsentPanelProps {
  text: AiConsentText
  pending: boolean
  failed: boolean
  onAgree: () => void
  onCancel: () => void
}

/** What goes to Google, who keeps what, and the choice to say no. Nothing is sent until the box is ticked and Agree is pressed. */
export function ConsentPanel({ text, pending, failed, onAgree, onCancel }: ConsentPanelProps) {
  const [agreed, setAgreed] = useState(false)
  return (
    <Card className="max-w-3xl space-y-3 p-4">
      <h2 className="flex items-center gap-2 text-sm font-semibold">
        <ShieldCheck aria-hidden className="size-4 text-primary" /> {text.title}
      </h2>
      <dl className="space-y-2">
        {text.points.map((point) => (
          <div key={point.heading}>
            <dt className="text-[13px] font-semibold">{point.heading}</dt>
            <dd className="text-[13px] text-muted-foreground">{point.text}</dd>
          </div>
        ))}
      </dl>
      <label className="flex min-h-8 items-start gap-2.5">
        <Checkbox checked={agreed} onCheckedChange={(v) => setAgreed(v === true)} className="mt-0.5" />
        <span className="text-[13px]">{text.checkbox}</span>
      </label>
      {failed ? <Alert variant="error">We could not save your choice. Please try again.</Alert> : null}
      <div className="flex flex-wrap gap-2">
        <Button onClick={onAgree} disabled={!agreed || pending}>
          {pending ? <LoaderCircle aria-hidden className="animate-spin" /> : null} Agree and continue
        </Button>
        <Button variant="outline" onClick={onCancel} disabled={pending}>
          Not now
        </Button>
      </div>
    </Card>
  )
}
