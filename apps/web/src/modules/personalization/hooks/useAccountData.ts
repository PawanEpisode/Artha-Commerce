import { useMutation, useQueryClient } from '@tanstack/react-query'

import { clearAllLocalData } from '~/lib/local-data'
import { useAuth } from '~/modules/auth'
import { track } from '~/modules/observability'

import { exportBlob, exportFileName, saveBlob } from '../lib/accountData'
import { deleteAccount, exportAccount } from '../lib/api'
import { rememberCompleted } from '../lib/completedCache'
import { clearLocalVisit } from '../lib/lastVisit'
import { notify } from '../lib/notify'

/** Fetches the student's data and hands it to the browser as a file. */
export function useExportData() {
  return useMutation({
    mutationFn: async () => {
      const data = await exportAccount()
      saveBlob(exportBlob(data), exportFileName())
    },
    onSuccess: () => {
      track('account_exported')
      notify.exportReady()
    },
  })
}

/**
 * Deletes the account, then leaves quietly: the session is dropped on this device, every cached answer and local copy
 * of this student is cleared, and the landing page opens. Errors stay on the mutation for the dialog to show.
 */
export function useDeleteAccount(onDeleted: () => void) {
  const qc = useQueryClient()
  const { user, signOut } = useAuth()
  return useMutation({
    mutationFn: (confirm: string) => deleteAccount(confirm),
    onSuccess: async () => {
      track('account_deleted')
      if (user) {
        rememberCompleted(user.id, false)
        clearLocalVisit(user.id)
        await clearAllLocalData(user.id)
      }
      await signOut({ silent: true })
      qc.clear()
      notify.accountDeleted()
      onDeleted()
    },
  })
}
