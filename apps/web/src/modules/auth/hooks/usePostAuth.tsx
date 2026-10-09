import { useNavigate } from '@tanstack/react-router'
import { createContext, type ReactNode, useCallback, useContext } from 'react'

import { safeNextPath } from '../lib/redirects'

/** Turns the `next` a sign-in carried into the page to open. Async because a richer rule may need to ask the API. */
export type PostAuthResolver = (next?: string) => Promise<string>

const plain: PostAuthResolver = (next) => Promise.resolve(safeNextPath(next))

const PostAuthContext = createContext<PostAuthResolver>(plain)

/**
 * Lets another module decide where a student lands after signing in (onboarding, last visit) without auth importing
 * it. Without a provider the answer is just the safe `next`, or `/app`.
 */
export function PostAuthProvider({ resolve, children }: { resolve: PostAuthResolver; children: ReactNode }) {
  return <PostAuthContext.Provider value={resolve}>{children}</PostAuthContext.Provider>
}

export const usePostAuthResolver = () => useContext(PostAuthContext)

/** `goAfterAuth(next)` resolves the destination, replaces the current history entry with it and returns it. */
export function useGoAfterAuth() {
  const resolve = usePostAuthResolver()
  const navigate = useNavigate()
  return useCallback(
    async (next?: string): Promise<string> => {
      let to: string
      try {
        to = await resolve(next)
      } catch {
        to = safeNextPath(next)
      }
      await navigate({ href: to, replace: true })
      return to
    },
    [resolve, navigate],
  )
}
