import { createFileRoute, useNavigate } from '@tanstack/react-router'

import { RegistryContainer } from '~/modules/material'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/settings/material')({
  head: () =>
    buildHead({
      title: 'Study Material & Institute Settings',
      description: 'Followed professional accounting bodies, edition preferences, and DPDP privacy settings.',
      path: '/app/settings/material',
      noindex: true,
    }),
  component: function MaterialSettingsRoute() {
    const navigate = useNavigate()

    return <RegistryContainer onBack={() => navigate({ to: '/app/material' })} />
  },
})
