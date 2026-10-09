import { useMutation, useQueryClient } from '@tanstack/react-query'

import { recallApi } from '../lib/api'
import { csvFileName, type CsvKind, fetchCsv, jsonFileName, saveBlob } from '../lib/dataExport'
import { clearRecallLocalData } from '../lib/localData'
import { useRecallUser } from './useRecallBasics'

export function useExportJson() {
  return useMutation({
    mutationFn: async () => {
      const data = await recallApi.exportJson()
      saveBlob(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }), jsonFileName())
    },
  })
}

export function useExportCsv() {
  return useMutation({
    mutationFn: async (kind: CsvKind) => {
      const { text, rows } = await fetchCsv(kind)
      saveBlob(new Blob([text], { type: 'text/csv;charset=utf-8' }), csvFileName(kind))
      return rows
    },
  })
}

/** Erases everything recall holds for her, then forgets what this device kept and every cached answer. */
export function useEraseAll(onErased: () => void) {
  const qc = useQueryClient()
  const userId = useRecallUser()
  return useMutation({
    mutationFn: (confirm: string) => recallApi.erase(confirm),
    onSuccess: async () => {
      if (userId) await clearRecallLocalData(userId)
      qc.removeQueries({ queryKey: ['recall'] })
      onErased()
    },
  })
}
