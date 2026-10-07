import {
  Alert,
  Button,
  FolderInput,
  SelectField,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
  Skeleton,
} from '@artha/design-system'

import type { PickerOption, PickerState } from '../lib/chapter-link'

interface ChapterPickerSheetProps {
  /** What the note is filed under now: "Taxation › GST", or "Unfiled". */
  currentLabel: string
  open: boolean
  onOpenChange: (open: boolean) => void
  state: PickerState
  onState: (change: Partial<PickerState>) => void
  subjects: readonly PickerOption[]
  chapters: readonly PickerOption[]
  topics: readonly PickerOption[]
  loadingSubjects: boolean
  loadingChapters: boolean
  loadingTopics: boolean
  failed: boolean
  onRetry: () => void
  /** A chapter is chosen, so Apply can run. */
  canApply: boolean
  onApply: () => void
  /** Unfile (shown only when the note is filed). */
  onClear?: () => void
  disabled?: boolean
  /** False when another control opens the sheet (the suggestion bar). */
  showTrigger?: boolean
}

const toOptions = (items: readonly PickerOption[], blank: string) => [
  { value: '', label: blank },
  ...items.map((i) => ({ value: i.id, label: i.name })),
]

/**
 * The F-02 picker: subject, then chapter, then an optional topic, all from the student's own syllabus. A button shows
 * where the note is filed; it opens a sheet so the page behind keeps its place (bottom sheet on phones).
 */
export function ChapterPickerSheet({
  currentLabel,
  open,
  onOpenChange,
  state,
  onState,
  subjects,
  chapters,
  topics,
  loadingSubjects,
  loadingChapters,
  loadingTopics,
  failed,
  onRetry,
  canApply,
  onApply,
  onClear,
  disabled,
  showTrigger = true,
}: ChapterPickerSheetProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      {showTrigger ? (
        <SheetTrigger asChild>
          <Button variant="outline" className="max-w-full justify-start" disabled={disabled}>
            <FolderInput aria-hidden />
            <span className="min-w-0 truncate">
              <span className="sr-only">Filed under: </span>
              {currentLabel}
            </span>
          </Button>
        </SheetTrigger>
      ) : null}
      <SheetContent side="bottom" className="max-h-[90dvh] overflow-y-auto sm:mx-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>File this note</SheetTitle>
          <SheetDescription>Pick a chapter from your syllabus. You can change it any time.</SheetDescription>
        </SheetHeader>
        {failed ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center gap-3">
              <span>We could not load your syllabus.</span>
              <Button size="sm" variant="outline" onClick={onRetry}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : loadingSubjects ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <div className="space-y-4">
            <div className="grid gap-2">
              <label htmlFor="picker-subject" className="text-sm font-medium">
                Subject
              </label>
              <SelectField
                id="picker-subject"
                value={state.subjectId}
                onValueChange={(subjectId) => onState({ subjectId })}
                options={toOptions(subjects, 'Choose a subject')}
              />
            </div>
            <div className="grid gap-2">
              <label htmlFor="picker-chapter" className="text-sm font-medium">
                Chapter
              </label>
              <SelectField
                id="picker-chapter"
                value={state.chapterId}
                disabled={!state.subjectId || loadingChapters}
                onValueChange={(chapterId) => onState({ chapterId })}
                options={toOptions(chapters, loadingChapters ? 'Loading chapters…' : 'Choose a chapter')}
              />
            </div>
            {state.chapterId && (loadingTopics || topics.length > 0) ? (
              <div className="grid gap-2">
                <label htmlFor="picker-topic" className="text-sm font-medium">
                  Topic (optional)
                </label>
                <SelectField
                  id="picker-topic"
                  value={state.topicId}
                  disabled={loadingTopics}
                  onValueChange={(topicId) => onState({ topicId })}
                  options={toOptions(topics, loadingTopics ? 'Loading topics…' : 'Whole chapter')}
                />
              </div>
            ) : null}
          </div>
        )}
        <SheetFooter>
          {onClear ? (
            <Button variant="ghost" onClick={onClear}>
              Move to Unfiled
            </Button>
          ) : null}
          <Button onClick={onApply} disabled={!canApply}>
            File here
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
