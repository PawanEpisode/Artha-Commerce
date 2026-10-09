import { useInfiniteQuery } from '@tanstack/react-query'

import { recallApi } from '../lib/api'
import { recallKeys } from '../lib/keys'

export interface CardFilters {
  subject_key?: string
  chapter_id?: string
  kind?: string
  tier?: string
  state?: string
  deck_id?: string
  q?: string
  status?: string
  sort?: string
}

/** The student's cards, a cursor page at a time (the cards screens in W10 build on this). */
export const useCards = (filters: CardFilters = {}, enabled = true) =>
  useInfiniteQuery({
    queryKey: recallKeys.cards(filters),
    queryFn: ({ pageParam }) => recallApi.cards({ ...filters, cursor: pageParam, limit: 50 }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled,
  })
