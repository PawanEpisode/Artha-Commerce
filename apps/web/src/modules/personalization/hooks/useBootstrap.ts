import { useQuery } from '@tanstack/react-query'

import { useAuth } from '~/modules/auth'

import { getBootstrap } from '../lib/api'
import { personalizationKeys } from '../lib/keys'

/** Cache key of the bootstrap for one student, shared by the hook and the post-sign-in resolver. */
export const bootstrapKey = (userId: string | null) => [...personalizationKeys.bootstrap, userId] as const

/**
 * The one `GET /me/` of the app: name, avatar, onboarding summary, course summary and last visit. Runs only for a
 * signed-in student; the header, the gate, the workspace and the scoped pages all read this same cache entry.
 */
export function useBootstrap() {
  const { user, loading } = useAuth()
  const query = useQuery({
    queryKey: bootstrapKey(user?.id ?? null),
    queryFn: getBootstrap,
    enabled: Boolean(user),
    staleTime: 60_000,
  })
  return { ...query, signedIn: Boolean(user), authLoading: loading }
}
