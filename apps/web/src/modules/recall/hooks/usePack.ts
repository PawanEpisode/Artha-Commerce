import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import { trackRecall } from '../lib/analytics'
import { recallApi } from '../lib/api'
import { eventStore, isStale, type StoredPack } from '../lib/eventStore'
import { recallKeys } from '../lib/keys'
import type { ApiPack } from '../lib/schemas'
import { useOnlineStatus, useRecallUser } from './useRecallBasics'

/** The server says a pack is good for 6 hours; after that a new one is fetched when the device is online. */
const bytesBucket = (n: number) => (n < 100_000 ? 'lt100k' : n < 500_000 ? 'lt500k' : 'gte500k')

export interface PackState {
  pack: ApiPack | null
  /** The stored pack is more than 48 hours old: cards may have changed elsewhere. */
  stale: boolean
  storedAt: number | null
  loading: boolean
  error: boolean
  refresh: () => Promise<void>
}

/** Downloads the offline pack when missing or past its expiry and keeps it in IndexedDB. Works from the stored copy offline. */
export function usePack(enabled = true): PackState {
  const userId = useRecallUser()
  const online = useOnlineStatus()
  const qc = useQueryClient()

  const query = useQuery({
    queryKey: [...recallKeys.pack, userId, online],
    enabled: enabled && userId !== null,
    staleTime: 5 * 60_000,
    // Reads this device's own storage, so it must run offline too (the default would pause it).
    networkMode: 'always',
    // Going offline changes the key: keep showing the pack in hand while the stored copy loads, so a session never blinks.
    placeholderData: keepPreviousData,
    queryFn: async (): Promise<StoredPack | null> => {
      if (!userId) return null
      const stored = await eventStore.loadPack(userId)
      const fresh = stored !== undefined && Date.parse(stored.pack.expires_at) > Date.now()
      if (!online || fresh) return stored ?? null
      try {
        const pack = await recallApi.pack()
        await eventStore.savePack(userId, pack)
        trackRecall('recall_pack_downloaded', {
          cards: pack.cards.length,
          bytes_bucket: bytesBucket(JSON.stringify(pack).length),
        })
        return (await eventStore.loadPack(userId)) ?? null
      } catch (error) {
        if (stored) return stored
        throw error
      }
    },
  })

  const refresh = useCallback(async () => {
    if (!userId || !online) return
    const pack = await recallApi.pack()
    await eventStore.savePack(userId, pack)
    await qc.invalidateQueries({ queryKey: recallKeys.pack })
  }, [userId, online, qc])

  const row = query.data ?? null
  return {
    pack: row?.pack ?? null,
    stale: row ? isStale(row) : false,
    storedAt: row?.storedAt ?? null,
    loading: query.isLoading,
    error: query.isError,
    refresh,
  }
}
