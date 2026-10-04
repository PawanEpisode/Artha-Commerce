import { createFileRoute } from '@tanstack/react-router'

import { AuthPage, SignupContainer } from '~/modules/auth'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/signup')({
  head: () =>
    buildHead({
      title: 'Create your account',
      description: 'Create a free ArthaCommerce account.',
      path: '/signup',
      noindex: true,
    }),
  component: () => (
    <AuthPage>
      <SignupContainer />
    </AuthPage>
  ),
})
