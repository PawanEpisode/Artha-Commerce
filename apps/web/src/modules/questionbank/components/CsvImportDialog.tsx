import {
  Alert,
  Button,
  Checkbox,
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  FileUp,
  Label,
  Textarea,
  toast,
} from '@artha/design-system'
import * as React from 'react'

import { type CsvImportResult, importQuestionsCsv } from '../lib/api'

interface CsvImportDialogProps {
  onSuccess?: (result: CsvImportResult) => void
  trigger?: React.ReactNode
}

const SAMPLE_CSV = `stem_md,kind,marks,option_a,option_b,option_c,option_d,correct_option,explanation_md
Which section of CGST Act deals with Input Tax Credit?,mcq_single,1,Section 15,Section 16,Section 17,Section 18,B,Section 16 covers ITC eligibility and conditions.
What is the standard GST rate for gold jewelry?,mcq_single,1,1%,3%,5%,12%,B,Gold attracts 3% IGST.`

export function CsvImportDialog({ onSuccess, trigger }: CsvImportDialogProps) {
  const [open, setOpen] = React.useState(false)
  const [csvText, setCsvText] = React.useState('')
  const [autoPublish, setAutoPublish] = React.useState(false)
  const [loading, setLoading] = React.useState(false)
  const [result, setResult] = React.useState<CsvImportResult | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  const handleImport = async () => {
    if (!csvText.trim()) {
      setError('Please paste CSV content to import.')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const res = await importQuestionsCsv(csvText, autoPublish)
      setResult(res)
      if (res.imported_count > 0) {
        toast.success(`Successfully imported ${res.imported_count} questions!`)
        onSuccess?.(res)
      } else {
        setError('No questions were imported. Please check CSV format.')
      }
    } catch {
      setError('Failed to import CSV. Please ensure you have editor permissions.')
    } finally {
      setLoading(false)
    }
  }

  const handleLoadSample = () => {
    setCsvText(SAMPLE_CSV)
    setError(null)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="outline" size="sm" className="gap-1.5">
            <FileUp className="size-4" />
            Bulk CSV Import
          </Button>
        )}
      </DialogTrigger>

      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Import Questions from CSV</DialogTitle>
          <DialogDescription>
            Bulk upload questions into the Question Bank. Supported kinds: mcq_single, mcq_multi, true_false, numeric.
          </DialogDescription>
        </DialogHeader>

        <div className="my-2 space-y-4">
          {error && <Alert variant="error">{error}</Alert>}

          {result && (
            <Alert variant={result.imported_count > 0 ? 'success' : 'info'}>
              Imported {result.imported_count} of {result.total_rows} questions.
              {result.errors.length > 0 && (
                <div className="mt-2 font-mono text-xs">
                  Errors:
                  <ul className="mt-1 list-disc pl-4">
                    {result.errors.slice(0, 3).map((err, idx) => (
                      <li key={idx}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </Alert>
          )}

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="csv-content">CSV Content</Label>
              <button type="button" onClick={handleLoadSample} className="text-xs text-primary hover:underline">
                Insert Sample Template
              </button>
            </div>
            <Textarea
              id="csv-content"
              rows={8}
              placeholder="Paste comma-separated rows with header: stem_md,kind,marks,option_a,option_b..."
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
              className="font-mono text-xs"
            />
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              id="auto-publish"
              checked={autoPublish}
              onCheckedChange={(checked) => setAutoPublish(Boolean(checked))}
            />
            <Label htmlFor="auto-publish" className="text-xs font-normal text-muted-foreground">
              Publish questions immediately (skip draft review)
            </Label>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:justify-end">
          <DialogClose asChild>
            <Button variant="outline" size="sm">
              Close
            </Button>
          </DialogClose>
          <Button size="sm" onClick={handleImport} disabled={loading || !csvText.trim()}>
            {loading ? 'Importing...' : 'Import Questions'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
