import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { AuthPage, ResetPasswordContainer } from '~/modules/auth'
import { pageHead } from '~/modules/seo'

export const Route = createFileRoute('/auth/reset-password')({
  validateSearch: z.object({ mode: z.enum(['invite']).optional().catch(undefined) }),
  head: () => pageHead('/auth/reset-password'),
  component: function ResetPasswordPage() {
    const { mode } = Route.useSearch()
    return (
      <AuthPage>
        <ResetPasswordContainer mode={mode} />
      </AuthPage>
    )
  },
})
