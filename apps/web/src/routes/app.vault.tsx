import { createFileRoute } from '@tanstack/react-router'

import { VaultContainer } from '~/modules/progression'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/vault')({
  head: () =>
    buildHead({
      title: 'Past Level Vault',
      description: 'Preserved notes, documents, and syllabus from your cleared academic tiers.',
      path: '/app/vault',
      noindex: true,
    }),
  component: VaultContainer,
})
