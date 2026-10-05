import {
  Alert,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Download,
  Trash2,
} from '@artha/design-system'
import { useRouter } from '@tanstack/react-router'
import { useState } from 'react'

import { DeleteAccountDialog } from '../components/DeleteAccountDialog'
import { useDeleteAccount, useExportData } from '../hooks/useAccountData'
import { CONFIRM_WORD, describeAccountError } from '../lib/accountData'

/** Account page "Your data" section (PRD section 7): download everything, or delete everything. */
export function DataSection() {
  const router = useRouter()
  const [confirming, setConfirming] = useState(false)
  const exporter = useExportData()
  const remove = useDeleteAccount(() => router.history.push('/'))

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Your data</CardTitle>
        <CardDescription>Take a copy of everything we hold about you, or delete your account.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">
            A JSON file with your profile, setup answers, coverage and study history.
          </p>
          <Button variant="outline" onClick={() => exporter.mutate()} disabled={exporter.isPending}>
            <Download aria-hidden /> {exporter.isPending ? 'Preparing…' : 'Download my data'}
          </Button>
          {exporter.isError ? (
            <Alert variant="error">{describeAccountError(exporter.error, 'export').message}</Alert>
          ) : null}
        </div>

        <div className="space-y-2 border-t border-border pt-6">
          <p className="text-sm text-muted-foreground">
            Deleting removes your account and all of the above for good. You will type {CONFIRM_WORD} to confirm.
          </p>
          <Button
            variant="danger"
            onClick={() => {
              remove.reset()
              setConfirming(true)
            }}
          >
            <Trash2 aria-hidden /> Delete my account
          </Button>
        </div>
      </CardContent>

      <DeleteAccountDialog
        open={confirming}
        onOpenChange={setConfirming}
        pending={remove.isPending}
        error={remove.error}
        onConfirm={() => remove.mutate(CONFIRM_WORD)}
      />
    </Card>
  )
}
