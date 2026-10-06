import type { UseQueryResult } from '@tanstack/react-query'

import type { WidgetState } from '../components/WidgetCard'

/** Maps a query to the three states a widget draws. Cached data stays on screen while a refetch fails. */
export function widgetState(query: Pick<UseQueryResult, 'data' | 'isPending' | 'isError'>): WidgetState {
  if (query.data !== undefined) return 'ready'
  if (query.isError) return 'error'
  return query.isPending ? 'loading' : 'ready'
}
