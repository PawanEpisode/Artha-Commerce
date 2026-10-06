import { QueryClient } from '@tanstack/react-query'
import { createRouter } from '@tanstack/react-router'

import { retryDelay, shouldRetry } from '~/lib/retry'
import { NotFound } from '~/modules/layout/NotFound'

import { routeTree } from './routeTree.gen'

export function getRouter() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { staleTime: 60_000, retry: shouldRetry, retryDelay, refetchOnWindowFocus: false },
    },
  })

  return createRouter({
    routeTree,
    context: { queryClient },
    scrollRestoration: true,
    defaultPreload: 'intent',
    defaultNotFoundComponent: NotFound,
  })
}

declare module '@tanstack/react-router' {
  interface Register {
    router: ReturnType<typeof getRouter>
  }
}
