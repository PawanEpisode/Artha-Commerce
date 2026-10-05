import { useQuery } from '@tanstack/react-query'

import { useAuth } from '~/modules/auth'

import { getBootstrap } from '../lib/api'
import { personalizationKeys } from '../lib/keys'

/**
 * The one `GET /me/` of the app: name, avatar, onboarding summary, course summary and last visit. Runs only for a
 * signed-in student; the header, the gate, the workspace and the scoped pages all read this same cache entry.
 */
export function useBootstrap() {
  const { user, loading } = useAuth()
  const query = useQuery({
    queryKey: [...personalizationKeys.bootstrap, user?.id ?? null],
    queryFn: getBootstrap,
    enabled: Boolean(user),
    staleTime: 60_000,
    retry: 1,
  })
  return { ...query, signedIn: Boolean(user), authLoading: loading }
}
