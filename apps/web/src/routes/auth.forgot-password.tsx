import { createFileRoute } from '@tanstack/react-router'

import { AuthPage, ForgotPasswordContainer } from '~/modules/auth'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/auth/forgot-password')({
  head: () =>
    buildHead({
      title: 'Reset your password',
      description: 'Reset your ArthaCommerce password.',
      path: '/auth/forgot-password',
      noindex: true,
    }),
  component: () => (
    <AuthPage>
      <ForgotPasswordContainer />
    </AuthPage>
  ),
})
