import { createFileRoute } from '@tanstack/react-router'

import { WorkspaceHome } from '~/modules/layout'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/')({
  head: () =>
    buildHead({ title: 'Workspace', description: 'Your ArthaCommerce workspace.', path: '/app', noindex: true }),
  component: WorkspaceHome,
})
