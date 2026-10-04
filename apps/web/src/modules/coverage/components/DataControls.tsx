import {
  Alert,
  Button,
  Card,
  Download,
  LoaderCircle,
  Popover,
  PopoverContent,
  PopoverTrigger,
  Trash2,
} from '@artha/design-system'

interface Props {
  exporting: boolean
  deleting: boolean
  error?: string
  deleted?: boolean
  onExport: () => void
  onDelete: () => void
}

/** Export and delete everything My Coverage stores (FR-29). Delete asks for one explicit confirmation. */
export function DataControls({ exporting, deleting, error, deleted, onExport, onDelete }: Props) {
  return (
    <Card className="space-y-4 p-6">
      <div>
        <h2 className="font-display text-xl font-bold">Your data</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Download everything My Coverage holds about you, or erase it.
        </p>
      </div>
      {error ? <Alert variant="error">{error}</Alert> : null}
      {deleted ? <Alert variant="success">All your coverage data has been deleted.</Alert> : null}
      <div className="flex flex-wrap gap-3">
        <Button variant="outline" onClick={onExport} disabled={exporting}>
          {exporting ? <LoaderCircle className="animate-spin" aria-hidden /> : <Download aria-hidden />}
          Export as JSON
        </Button>
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" disabled={deleting}>
              <Trash2 aria-hidden /> Delete my coverage data
            </Button>
          </PopoverTrigger>
          <PopoverContent className="space-y-3">
            <p className="font-semibold">Delete everything?</p>
            <p className="text-muted-foreground">
              This removes your enrolments, progress, logs and settings. It cannot be undone. Consider exporting first.
            </p>
            <Button className="w-full" onClick={onDelete}>
              Yes, delete it all
            </Button>
          </PopoverContent>
        </Popover>
      </div>
    </Card>
  )
}
