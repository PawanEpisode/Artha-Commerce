import { useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useCallback } from 'react'

import { PostAuthProvider, type PostAuthResolver, safeNextPath, useAuth } from '~/modules/auth'
import { useFeatureFlag } from '~/modules/observability'

import { bootstrapKey } from '../hooks/useBootstrap'
import { getBootstrap } from '../lib/api'
import { resolvePostAuthDestination } from '../lib/destination'

/**
 * Plugs the destination rules (PRD 5.1) into every sign-in surface. Mounted once under the auth provider. When the
 * flag is off, or the API cannot answer, it falls back to the plain safe `next`; the /app guard still has the last word.
 */
export function PersonalizedPostAuth({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const { user } = useAuth()
  const enabled = useFeatureFlag('personalization')
  const userId = user?.id ?? null

  const resolve = useCallback<PostAuthResolver>(
    async (next) => {
      if (!enabled || !userId) return safeNextPath(next)
      try {
        const facts = await qc.fetchQuery({ queryKey: bootstrapKey(userId), queryFn: getBootstrap, staleTime: 0 })
        return resolvePostAuthDestination(facts, next)
      } catch {
        return safeNextPath(next)
      }
    },
    [enabled, userId, qc],
  )

  return <PostAuthProvider resolve={resolve}>{children}</PostAuthProvider>
}
