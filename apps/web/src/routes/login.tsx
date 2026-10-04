import { createFileRoute } from '@tanstack/react-router'
import { Container } from '~/design-system'
import { LoginContainer } from '~/modules/auth'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/login')({
  head: () => buildHead({ title: 'Sign in', description: 'Sign in to ArthaCommerce.', path: '/login', noindex: true }),
  component: () => (
    <Container className="grid min-h-[70vh] place-items-center py-16">
      <LoginContainer />
    </Container>
  ),
})
