import { Container } from '@artha/design-system'
import { createFileRoute } from '@tanstack/react-router'

import { AccountContainer } from '~/modules/auth'
import { ProfileSection } from '~/modules/personalization'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/account')({
  head: () =>
    buildHead({
      title: 'Account',
      description: 'Your ArthaCommerce account settings.',
      path: '/app/account',
      noindex: true,
    }),
  component: () => (
    <Container className="py-10 sm:py-14">
      <AccountContainer profileSlot={<ProfileSection />} />
    </Container>
  ),
})
