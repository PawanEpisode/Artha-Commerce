import { useMutation } from '@tanstack/react-query'

import { trackRecall } from '../lib/analytics'
import { type ImportBody, recallApi } from '../lib/api'
import { useRefresh } from './useCardScreens'

/**
 * Paste or CSV import. The preview (`dry_run`) writes nothing; the real call creates the valid rows in one step, and the same
 * `client_id` makes a retry after a dropped answer safe (the rows come back as already imported). Product events carry counts only.
 */
export function useImportCards() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (body: ImportBody) => recallApi.importCards(body),
    onSuccess: (result) => {
      if (result.dry_run) {
        trackRecall('recall_import_previewed', { rows: result.total, valid: result.valid, invalid: result.invalid })
        return
      }
      trackRecall('recall_import_done', { rows: result.total, created: result.created, invalid: result.invalid })
      refresh()
    },
  })
}
