import {
  Alert,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Skeleton,
} from '@artha/design-system'

import { ApiError } from '~/lib/api'

import { AvatarEditor } from '../components/AvatarEditor'
import { IdentityAvatar } from '../components/IdentityAvatar'
import { NameForm } from '../components/NameForm'
import { useBootstrap } from '../hooks/useBootstrap'
import { useOnline } from '../hooks/useOnline'
import { useUpdateName } from '../hooks/useProfileMutations'

/** Account page "Profile" section (PRD 5.5): name and picture, with every state of the avatar flow. */
export function ProfileSection() {
  const { data, isPending, isError, refetch } = useBootstrap()
  const online = useOnline()
  const rename = useUpdateName()

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Profile</CardTitle>
        <CardDescription>Your name and picture. Only you see them, on this account.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {isPending ? (
          <div className="flex items-center gap-4" aria-busy>
            <Skeleton className="size-24 rounded-full" />
            <Skeleton className="h-11 flex-1" />
          </div>
        ) : isError || !data ? (
          <Alert variant="error">
            <div className="space-y-2">
              <p>We could not load your profile.</p>
              <Button size="sm" variant="outline" onClick={() => void refetch()}>
                Try again
              </Button>
            </div>
          </Alert>
        ) : (
          <>
            <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
              <IdentityAvatar size={96} />
              <div className="min-w-0 flex-1">
                <NameForm
                  key={data.full_name}
                  value={data.full_name}
                  pending={rename.isPending}
                  disabled={!online}
                  serverError={nameError(rename.error)}
                  onSave={(name) => rename.mutate(name)}
                />
                {!online ? (
                  <p className="mt-2 text-sm text-muted-foreground">You are offline. Name changes need a connection.</p>
                ) : null}
              </div>
            </div>
            <AvatarEditor avatar={data.avatar} />
          </>
        )}
      </CardContent>
    </Card>
  )
}

/** The server's message for the name field (400 `invalid`), if that is what failed. */
function nameError(error: unknown): string | undefined {
  if (!error) return undefined
  if (!(error instanceof ApiError)) return 'We could not save your name. Try again.'
  const details = (error.body as { error?: { details?: { full_name?: string[] } } } | undefined)?.error?.details
  return details?.full_name?.[0] ?? 'We could not save your name. Try again.'
}
