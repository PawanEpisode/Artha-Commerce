import { Alert, Button, Card, ShieldCheck } from '@artha/design-system'

import type { AiConsent } from '../lib/schemas'

/**
 * What the student agrees to before the AI reads anything of hers. The wording comes from the server (one source, versioned),
 * so the version she agrees to is the version she read.
 */
export function AiConsentPanel({
  consent,
  pending,
  error,
  onAgree,
}: {
  consent: AiConsent
  pending: boolean
  error: string | null
  onAgree: () => void
}) {
  return (
    <Card className="space-y-4 p-5 sm:p-6" aria-labelledby="ai-consent-title">
      <div className="flex items-start gap-3">
        <ShieldCheck aria-hidden className="mt-1 size-6 shrink-0 text-primary" />
        <h2 id="ai-consent-title" className="text-xl font-bold">
          {consent.title}
        </h2>
      </div>
      <dl className="space-y-3">
        {consent.points.map((p) => (
          <div key={p.heading}>
            <dt className="font-semibold">{p.heading}</dt>
            <dd className="text-muted-foreground">{p.text}</dd>
          </div>
        ))}
      </dl>
      {error ? <Alert variant="error">{error}</Alert> : null}
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={onAgree} disabled={pending}>
          {pending ? 'Saving…' : 'I agree'}
        </Button>
        <p className="text-sm text-muted-foreground">You can withdraw this any time from this page.</p>
      </div>
    </Card>
  )
}
