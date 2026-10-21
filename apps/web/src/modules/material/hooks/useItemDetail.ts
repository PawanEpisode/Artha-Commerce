import { useCallback, useEffect, useState } from 'react'

import { fetchItemDetail, reportMaterialItem, updateItemProgress } from '../lib/api'
import type { MaterialItem, MaterialReportPayload, ProgressState } from '../lib/types'

export function useItemDetail(itemId: string) {
  const [item, setItem] = useState<MaterialItem | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const reload = useCallback(() => {
    setIsLoading(true)
    setError(null)

    fetchItemDetail(itemId)
      .then((data) => {
        setItem(data)
        setIsLoading(false)
      })
      .catch((err) => {
        setError(err)
        setIsLoading(false)
      })
  }, [itemId])

  useEffect(() => {
    reload()
  }, [reload])

  const setProgress = async (nextState: ProgressState, note?: string) => {
    if (!item) return
    const prev = { ...item }

    setItem({
      ...item,
      progress: nextState,
      note: note !== undefined ? note : item.note,
      revised_since_done: false,
    })

    try {
      await updateItemProgress(item.id, {
        state: nextState,
        note,
        client_ts: new Date().toISOString(),
      })
    } catch (err) {
      setItem(prev)
      throw err
    }
  }

  const report = async (payload: MaterialReportPayload) => {
    return reportMaterialItem(itemId, payload)
  }

  return {
    item,
    isLoading,
    error,
    reload,
    setProgress,
    report,
  }
}
