import { toast } from '@artha/design-system'

import { AttestationPanel } from '../components/AttestationPanel'
import { useAttest } from '../hooks/useHistory'
import { useOnlineStatus } from '../hooks/useRecallBasics'
import { errorText } from '../lib/errors'
import type { RecallCardDetail } from '../lib/schemas'

/** The "my own words" statement on the card page. Nothing is shown for a card it does not apply to. */
export function AttestationSection({ card }: { card: RecallCardDetail }) {
  const online = useOnlineStatus()
  const attest = useAttest(card.id)
  if (!card.attestation.required) return null
  return (
    <AttestationPanel
      attested={card.attestation.attested}
      pending={attest.isPending}
      offline={!online}
      error={attest.isError ? errorText(attest.error, 'We could not save that. Please try again.') : null}
      onChange={(own) =>
        attest.mutate(own, {
          onSuccess: (r) =>
            toast.success(r.attested ? 'Saved. This card can be shared.' : 'Taken back. This card is private.'),
        })
      }
    />
  )
}
