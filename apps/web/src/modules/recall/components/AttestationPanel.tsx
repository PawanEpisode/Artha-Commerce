import { Alert, Button, ShieldCheck } from '@artha/design-system'

import { attestationText } from '../lib/history'

interface Props {
  attested: boolean
  pending: boolean
  offline: boolean
  error: string | null
  onChange: (ownWords: boolean) => void
}

/** "Are these your own words?": the statement that lets a card made from a selection be included when she shares a deck. */
export function AttestationPanel({ attested, pending, offline, error, onChange }: Props) {
  const text = attestationText(attested)
  return (
    <section aria-labelledby="attest-heading" className="space-y-3 rounded-2xl border border-border bg-card p-4 sm:p-5">
      <h2 id="attest-heading" className="flex items-center gap-2 font-display text-xl font-bold">
        <ShieldCheck aria-hidden className="size-5 text-primary" />
        {text.title}
      </h2>
      <p className="text-sm text-muted-foreground">{text.help}</p>
      {error ? <Alert variant="error">{error}</Alert> : null}
      <Button
        variant={attested ? 'outline' : 'default'}
        size="lg"
        loading={pending}
        disabled={offline}
        onClick={() => onChange(!attested)}
      >
        {attested ? 'Take that back' : 'Yes, these are my own words'}
      </Button>
      {offline ? <p className="text-sm text-muted-foreground">This needs the internet.</p> : null}
    </section>
  )
}
