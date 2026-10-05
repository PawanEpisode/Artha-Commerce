import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { AuthPage, ConfirmContainer } from '~/modules/auth'
import { pageHead } from '~/modules/seo'

/** Target of the links in our auth emails (see packages/email-templates). */
export const Route = createFileRoute('/auth/confirm')({
  validateSearch: z.object({
    token_hash: z.string().optional().catch(undefined),
    type: z.string().optional().catch(undefined),
    next: z.string().optional().catch(undefined),
  }),
  head: () => pageHead('/auth/confirm'),
  component: function ConfirmPage() {
    const { token_hash, type, next } = Route.useSearch()
    return (
      <AuthPage>
        <ConfirmContainer tokenHash={token_hash} type={type} next={next} />
      </AuthPage>
    )
  },
})
