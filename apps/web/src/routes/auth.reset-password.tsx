import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { AuthPage, ResetPasswordContainer } from '~/modules/auth'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/auth/reset-password')({
  validateSearch: z.object({ mode: z.enum(['invite']).optional().catch(undefined) }),
  head: () =>
    buildHead({
      title: 'Choose a new password',
      description: 'Choose a new ArthaCommerce password.',
      path: '/auth/reset-password',
      noindex: true,
    }),
  component: function ResetPasswordPage() {
    const { mode } = Route.useSearch()
    return (
      <AuthPage>
        <ResetPasswordContainer mode={mode} />
      </AuthPage>
    )
  },
})
