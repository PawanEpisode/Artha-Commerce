import { Alert, Button, Card, LoaderCircle, UsageBar } from '@artha/design-system'
import { useState } from 'react'

import { useAiAvailable, useAiConsent, useWithdrawConsent } from '../hooks/useAi'
import { useUsage } from '../hooks/useNotesQueries'
import { summaryAllowance } from '../lib/ai-copy'
import { notify } from '../lib/notify'

/** Settings: where the student stands with AI help, this month's summaries, and the way to take consent back. Hidden while AI is off. */
export function AiSettingsContainer() {
  const ai = useAiAvailable()
  const consent = useAiConsent(ai.flag)
  const usage = useUsage()
  const withdraw = useWithdrawConsent()
  const [confirming, setConfirming] = useState(false)
  if (!ai.available || !consent.data) return null

  const allowance = summaryAllowance(usage.data)
  const done = () => {
    setConfirming(false)
    notify.aiWithdrawn()
  }
  return (
    <Card className="space-y-4 p-6">
      <h2 className="font-display text-xl font-bold">AI help</h2>
      <p className="text-sm text-muted-foreground">
        {consent.data.consented
          ? 'You agreed to send your notes, highlights and the page pictures you choose to Google.'
          : 'You have not agreed to AI help, so nothing is sent.'}
      </p>
      {allowance && allowance.limit > 0 ? (
        <UsageBar label="Summaries this month" used={allowance.used} limit={allowance.limit} fullText="All used" />
      ) : null}
      {consent.data.consented ? (
        confirming ? (
          <Alert variant="error">
            <span className="flex flex-col gap-3">
              <span>Withdrawing deletes unsaved AI drafts and stops waiting requests. Notes you saved stay.</span>
              <span className="flex flex-wrap gap-3">
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => withdraw.mutate(undefined, { onSuccess: done })}
                  disabled={withdraw.isPending}
                >
                  {withdraw.isPending ? <LoaderCircle aria-hidden className="animate-spin" /> : null} Withdraw consent
                </Button>
                <Button variant="outline" size="sm" onClick={() => setConfirming(false)} disabled={withdraw.isPending}>
                  Keep it
                </Button>
              </span>
            </span>
          </Alert>
        ) : (
          <Button variant="outline" onClick={() => setConfirming(true)}>
            Withdraw consent
          </Button>
        )
      ) : null}
      {withdraw.isError ? <Alert variant="error">We could not withdraw consent. Please try again.</Alert> : null}
    </Card>
  )
}
