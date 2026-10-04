import { Button, Container } from '@artha/design-system'
import { createFileRoute, Link } from '@tanstack/react-router'

import { useAuth } from '~/modules/auth'
import { useFeatureFlag } from '~/modules/observability'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/')({
  head: () =>
    buildHead({ title: 'Workspace', description: 'Your ArthaCommerce workspace.', path: '/app', noindex: true }),
  component: Workspace,
})

// Placeholder: the real workspace shell is the next milestone.
function Workspace() {
  const { user } = useAuth()
  const coverageOn = useFeatureFlag('syllabus_coverage')
  return (
    <Container className="py-14 sm:py-20">
      <h1 className="text-3xl font-extrabold">Your workspace</h1>
      <p className="mt-3 text-muted-foreground">
        Signed in as {user?.email}. Dashboard, planner and tracker land here next.
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        {coverageOn ? (
          <Button asChild>
            <Link to="/app/syllabus">My coverage</Link>
          </Button>
        ) : null}
        <Button variant="outline" asChild>
          <Link to="/app/account">Account and settings</Link>
        </Button>
      </div>
    </Container>
  )
}
