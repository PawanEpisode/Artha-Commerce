import { useCallback, useEffect, useState } from 'react'

import { fetchProviders, fetchUserFollowedProviders, followProvider, unfollowProvider } from '../lib/api'
import type { Provider, UserProviderFollow } from '../lib/types'

export function useRegistry() {
  const [providers, setProviders] = useState<Provider[]>([])
  const [followed, setFollowed] = useState<UserProviderFollow[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const reload = useCallback(() => {
    setIsLoading(true)
    setError(null)

    Promise.all([fetchProviders(), fetchUserFollowedProviders().catch(() => [])])
      .then(([allProviders, userFollowed]) => {
        setProviders(allProviders || [])
        setFollowed(userFollowed || [])
        setIsLoading(false)
      })
      .catch((err) => {
        setError(err)
        setIsLoading(false)
      })
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  const follow = async (providerId: string, isPrimary = false) => {
    try {
      const created = await followProvider(providerId, isPrimary)
      setFollowed((prev) => [...prev, created])
    } catch (err) {
      console.error('Failed to follow provider', err)
      throw err
    }
  }

  const unfollow = async (userProviderId: string) => {
    try {
      await unfollowProvider(userProviderId)
      setFollowed((prev) => prev.filter((p) => p.id !== userProviderId))
    } catch (err) {
      console.error('Failed to unfollow provider', err)
      throw err
    }
  }

  return {
    providers,
    followed,
    isLoading,
    error,
    reload,
    follow,
    unfollow,
  }
}
