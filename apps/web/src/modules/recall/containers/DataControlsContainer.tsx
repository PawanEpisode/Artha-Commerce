import { toast } from '@artha/design-system'
import { useState } from 'react'

import { DataControls } from '../components/DataControls'
import { EraseDialog } from '../components/EraseDialog'
import { useEraseAll, useExportCsv, useExportJson } from '../hooks/useDataControls'
import { errorText } from '../lib/errors'

/** Export and erase of her revision data. Rendered by the settings screen, with or without the feature switched on. */
export function DataControlsContainer() {
  const [erasing, setErasing] = useState(false)
  const json = useExportJson()
  const csv = useExportCsv()
  const erase = useEraseAll(() => {
    setErasing(false)
    toast.success('Your revision data was erased.')
  })
  const busy = json.isPending ? 'json' : csv.isPending ? csv.variables : null
  const failure = json.isError
    ? errorText(json.error, 'Could not download your data. Please try again.')
    : csv.isError
      ? errorText(csv.error, 'Could not download that file. Please try again.')
      : null
  return (
    <>
      <DataControls
        busy={busy}
        error={failure}
        onExportJson={() => json.mutate(undefined, { onSuccess: () => toast.success('Your data was downloaded.') })}
        onExportCsv={(kind) =>
          csv.mutate(kind, { onSuccess: (rows) => toast.success(`Downloaded ${rows} ${rows === 1 ? 'row' : 'rows'}.`) })
        }
        onErase={() => {
          erase.reset()
          setErasing(true)
        }}
      />
      <EraseDialog
        open={erasing}
        onOpenChange={setErasing}
        pending={erase.isPending}
        error={erase.isError ? errorText(erase.error, 'Could not erase your data. Please try again.') : null}
        onConfirm={(word) => erase.mutate(word)}
      />
    </>
  )
}
