import { useCallback, useEffect, useState } from 'react'

import { fetchChapterItems, reportMaterialItem, updateItemProgress } from '../lib/api'
import type {
  ChapterItemsResponse,
  ChapterSummary,
  MaterialItem,
  MaterialReportPayload,
  ProgressState,
} from '../lib/types'

export function useChapterItems(workKey: string, chapterKey: string) {
  const [data, setData] = useState<ChapterItemsResponse | null>(null)
  const [items, setItems] = useState<MaterialItem[]>([])
  const [summary, setSummary] = useState<ChapterSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const reload = useCallback(() => {
    setIsLoading(true)
    setError(null)

    fetchChapterItems(workKey, chapterKey)
      .then((res) => {
        setData(res)
        setItems(res.items || [])
        setSummary(res.summary)
        setIsLoading(false)
      })
      .catch((err) => {
        setError(err)
        setIsLoading(false)
      })
  }, [workKey, chapterKey])

  useEffect(() => {
    reload()
  }, [reload])

  const setProgress = async (itemId: string, nextState: ProgressState, note?: string) => {
    // Snapshot for rollback
    const previousItems = [...items]
    const previousSummary = summary ? { ...summary } : null

    // Optimistic update
    const updatedItems = items.map((item) => {
      if (item.id === itemId) {
        return {
          ...item,
          progress: nextState,
          note: note !== undefined ? note : item.note,
          revised_since_done: false, // reset badge on student update
        }
      }
      return item
    })

    setItems(updatedItems)

    // Recalculate summary locally
    if (previousSummary) {
      const counts = { done: 0, revise: 0, to_do: 0 }
      updatedItems.forEach((i) => {
        const st = i.progress || 'to_do'
        counts[st] = (counts[st] || 0) + 1
      })
      const total = updatedItems.length
      setSummary({
        ...previousSummary,
        done: counts.done,
        revise: counts.revise,
        to_do: counts.to_do,
        completion_pct: total > 0 ? Math.round((counts.done / total) * 100) : 0,
      })
    }

    try {
      await updateItemProgress(itemId, {
        state: nextState,
        note,
        client_ts: new Date().toISOString(),
      })
    } catch (err) {
      console.error('Failed to update progress on server, rolling back', err)
      setItems(previousItems)
      setSummary(previousSummary)
      throw err
    }
  }

  const reportItem = async (itemId: string, payload: MaterialReportPayload) => {
    return reportMaterialItem(itemId, payload)
  }

  return {
    data,
    items,
    summary,
    isLoading,
    error,
    reload,
    setProgress,
    reportItem,
  }
}
