import { FolderInput } from '@artha/design-system'

import type { PickerState } from '../../../lib/chapter-link'
import { filingProblem } from '../../../lib/document-draft'
import { ChapterFields, type ChapterFieldsProps } from '../../ChapterFields'

interface FilingStepProps extends Omit<ChapterFieldsProps, 'idPrefix' | 'allowAll' | 'subjectBlank' | 'withTopic'> {
  state: PickerState
  /** Where it will be filed in words: "Taxation › All chapters", or "Unfiled". */
  summary: string
  /** Why the syllabus could not be read, when it could not. */
  failed?: boolean
}

/**
 * Where the PDF belongs in the student's syllabus: a subject (only their own papers), then one chapter or All chapters for
 * the whole subject. Leaving the subject empty keeps the PDF Unfiled, which is fine and can be changed any time.
 */
export function FilingStep({ summary, failed, ...fields }: FilingStepProps) {
  const problem = filingProblem(fields.state)
  return (
    <div className="space-y-5">
      <ChapterFields {...fields} idPrefix="doc-filing" allowAll subjectBlank="No subject (Unfiled)" />
      {problem ? (
        <p role="alert" className="text-sm font-medium text-error-fg">
          {problem}
        </p>
      ) : null}
      {failed ? (
        <p role="alert" className="text-sm font-medium text-error-fg">
          We could not load your syllabus. Check your connection and open this step again.
        </p>
      ) : null}
      <p className="flex min-w-0 items-start gap-2 rounded-xl bg-muted px-3 py-2 text-sm">
        <FolderInput aria-hidden className="mt-0.5 size-4 shrink-0" />
        <span className="min-w-0 break-words">
          <span className="text-muted-foreground">Filed under: </span>
          <span className="font-semibold">{summary}</span>
        </span>
      </p>
      <p className="text-sm text-muted-foreground">
        Pick All chapters when the PDF covers the whole subject. Marks on pages that have no page range of their own are
        filed under the chapter you pick here. You can change this any time.
      </p>
    </div>
  )
}
