import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { AuthPage, LoginContainer } from '~/modules/auth'
import { pageHead } from '~/modules/seo'

export const Route = createFileRoute('/login')({
  validateSearch: z.object({
    method: z.enum(['code', 'password']).optional().catch(undefined),
    next: z.string().optional().catch(undefined),
  }),
  head: () => pageHead('/login'),
  component: function LoginPage() {
    const { method, next } = Route.useSearch()
    const navigate = Route.useNavigate()
    return (
      <AuthPage>
        <LoginContainer
          method={method ?? 'code'}
          next={next}
          onMethodChange={(m) => void navigate({ search: (prev) => ({ ...prev, method: m }), replace: true })}
        />
      </AuthPage>
    )
  },
})
