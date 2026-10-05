import { createFileRoute } from '@tanstack/react-router'

import { AuthPage, SignupContainer } from '~/modules/auth'
import { pageHead } from '~/modules/seo'

export const Route = createFileRoute('/signup')({
  head: () => pageHead('/signup'),
  component: () => (
    <AuthPage>
      <SignupContainer />
    </AuthPage>
  ),
})
