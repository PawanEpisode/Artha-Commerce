import { useCallback, useEffect, useState } from 'react'

import { dismissEditionBanner, fetchUserEdition, fetchWork, setUserEdition } from '../lib/api'
import type { EditionDetail, UserEditionSelection, Work } from '../lib/types'

export function useWorkDetail(workKey: string) {
  const [work, setWork] = useState<(Work & { editions: EditionDetail[] }) | null>(null)
  const [userEdition, setUserEditionState] = useState<UserEditionSelection | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const reload = useCallback(() => {
    setIsLoading(true)
    setError(null)

    Promise.all([fetchWork(workKey), fetchUserEdition(workKey).catch(() => null)])
      .then(([workData, editionData]) => {
        setWork(workData)
        setUserEditionState(editionData)
        setIsLoading(false)
      })
      .catch((err) => {
        setError(err)
        setIsLoading(false)
      })
  }, [workKey])

  useEffect(() => {
    reload()
  }, [reload])

  const selectEdition = async (editionKey: string) => {
    try {
      const updated = await setUserEdition(workKey, editionKey)
      setUserEditionState(updated)
    } catch (err) {
      console.error('Failed to update edition selection', err)
      throw err
    }
  }

  const dismissBanner = async () => {
    try {
      await dismissEditionBanner(workKey)
    } catch (err) {
      console.error('Failed to dismiss edition banner', err)
    }
  }

  return {
    work,
    userEdition,
    isLoading,
    error,
    reload,
    selectEdition,
    dismissBanner,
  }
}
