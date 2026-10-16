import { createFileRoute } from '@tanstack/react-router'

import { AccountContainer } from '~/modules/auth'
import { DataSection, ProfileSection } from '~/modules/personalization'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/account')({
  head: () =>
    buildHead({
      title: 'Account',
      description: 'Your ArthaCommerce account settings.',
      path: '/app/account',
      noindex: true,
    }),
  component: () => <AccountContainer profileSlot={<ProfileSection />} dataSlot={<DataSection />} />,
})
