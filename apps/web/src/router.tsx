import { toast, toastApiError } from '@artha/design-system'
import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'
import { createRouter } from '@tanstack/react-router'

import { retryDelay, shouldRetry } from '~/lib/retry'
import { NotFound } from '~/modules/layout/NotFound'

import { routeTree } from './routeTree.gen'

export function getRouter() {
  const mutationCache = new MutationCache({
    onError: (error, _variables, _context, mutation) => {
      if (mutation.meta?.silent) return
      const fallback =
        typeof mutation.meta?.errorMessage === 'string'
          ? mutation.meta.errorMessage
          : 'Action failed. Please try again.'
      toastApiError(error, fallback)
    },
    onSuccess: (data, _variables, _context, mutation) => {
      if (mutation.meta?.silent) return
      if (typeof mutation.meta?.successMessage === 'string') {
        toast.success(mutation.meta.successMessage)
        return
      }
      if (typeof mutation.meta?.successMessage === 'function') {
        const msg = (mutation.meta.successMessage as (d: unknown) => unknown)(data)
        if (typeof msg === 'string' && msg) {
          toast.success(msg)
          return
        }
      }
      if (
        typeof data === 'object' &&
        data !== null &&
        'message' in data &&
        typeof (data as { message?: unknown }).message === 'string'
      ) {
        const msg = (data as { message: string }).message
        if (msg && !['ok', 'success', 'Request failed.'].includes(msg)) {
          toast.success(msg)
        }
      }
    },
  })

  const queryCache = new QueryCache({
    onError: (error, query) => {
      if (query.meta?.toastError) {
        const fallback =
          typeof query.meta.errorMessage === 'string' ? query.meta.errorMessage : 'Could not load data. Please refresh.'
        toastApiError(error, fallback)
      }
    },
  })

  const queryClient = new QueryClient({
    mutationCache,
    queryCache,
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
