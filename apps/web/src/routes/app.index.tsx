import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { WorkspaceHome } from '~/modules/layout'
import { RestoreOnLanding } from '~/modules/personalization'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/')({
  validateSearch: z.object({ from: z.literal('landing').optional().catch(undefined) }),
  head: () =>
    buildHead({ title: 'Workspace', description: 'Your ArthaCommerce workspace.', path: '/app', noindex: true }),
  component: function WorkspaceRoute() {
    const { from } = Route.useSearch()
    return (
      <RestoreOnLanding active={from === 'landing'}>
        <WorkspaceHome />
      </RestoreOnLanding>
    )
  },
})
