import { useQuery } from '@tanstack/react-query'

import { fetchMyCards, isFeatureDisabled } from '../lib/api'
import { amendmentsKeys } from '../lib/keys'
import type { CardFilter, MyCard } from '../lib/types'

export interface CardsResult {
  cards: MyCard[]
  total_count: number
  has_more: boolean
  next_cursor: string | null
}

export function useMyCards(filter: CardFilter = {}, cursor: string | null = null, enabled = true) {
  return useQuery<CardsResult>({
    queryKey: amendmentsKeys.cards(filter as Record<string, unknown>, cursor),
    queryFn: () => fetchMyCards(filter, cursor),
    enabled,
    staleTime: 30_000,
    retry: (count, error) => !isFeatureDisabled(error) && count < 2,
  })
}
