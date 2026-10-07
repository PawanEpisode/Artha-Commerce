import { Container } from '@artha/design-system'
import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { UnsubscribeContainer } from '~/modules/notifications'
import { pageHead } from '~/modules/seo'

/** Target of the "Unsubscribe" link in the weekly email. Public, signed link in `t`, never indexed. */
export const Route = createFileRoute('/unsubscribe')({
  validateSearch: z.object({ t: z.string().optional().catch(undefined) }),
  head: () => pageHead('/unsubscribe'),
  component: function UnsubscribePage() {
    const { t } = Route.useSearch()
    return (
      <Container className="grid min-h-[70vh] place-items-center py-10 sm:py-16">
        <div className="w-full max-w-md">
          <UnsubscribeContainer token={t} />
        </div>
      </Container>
    )
  },
})
