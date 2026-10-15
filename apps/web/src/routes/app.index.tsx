import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { RestoreOnLanding } from '~/modules/personalization'
import { buildHead } from '~/modules/seo'
import { TodayHomeRedirect } from '~/modules/today'
import { WorkspaceHomeContainer } from '~/modules/workspace'

export const Route = createFileRoute('/app/')({
  validateSearch: z.object({
    from: z.literal('landing').optional().catch(undefined),
    /** `home` opens the workspace home even when Today is on (Today's own "back" link), so the redirect never traps. */
    home: z.literal(true).optional().catch(undefined),
  }),
  head: () =>
    buildHead({ title: 'Workspace', description: 'Your ArthaCommerce workspace.', path: '/app', noindex: true }),
  component: function WorkspaceRoute() {
    const { from, home } = Route.useSearch()
    return (
      <RestoreOnLanding active={from === 'landing'}>
        <TodayHomeRedirect skip={home === true}>
          <WorkspaceHomeContainer />
        </TodayHomeRedirect>
      </RestoreOnLanding>
    )
  },
})
