import { createFileRoute } from '@tanstack/react-router'

import { AuthPage, ForgotPasswordContainer } from '~/modules/auth'
import { pageHead } from '~/modules/seo'

export const Route = createFileRoute('/auth/forgot-password')({
  head: () => pageHead('/auth/forgot-password'),
  component: () => (
    <AuthPage>
      <ForgotPasswordContainer />
    </AuthPage>
  ),
})
