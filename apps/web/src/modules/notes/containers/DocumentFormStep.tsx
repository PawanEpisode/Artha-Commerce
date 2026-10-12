import { Alert } from '@artha/design-system'

import { useOnline } from '~/modules/personalization'

import { DetailsStep } from '../components/library/steps/DetailsStep'
import { FilingStep } from '../components/library/steps/FilingStep'
import type { DocumentFormData } from '../hooks/useDocumentFormData'
import { useNoteActions } from '../hooks/useNoteActions'
import { useTags } from '../hooks/useNotesQueries'
import type { OutlineNode } from '../lib/chapter-inheritance'
import { linkFromSelection, linkLabel, pickerReduce } from '../lib/chapter-link'
import type { DocumentDraft, FormStepId } from '../lib/document-draft'
import type { RowProblems } from '../lib/page-ranges'
import { RangesStepContainer } from './RangesStepContainer'

interface DocumentFormStepProps {
  step: FormStepId
  draft: DocumentDraft
  onDraft: (change: Partial<DocumentDraft>) => void
  form: DocumentFormData
  pageCount: number | null
  outline?: readonly OutlineNode[] | null
  serverProblems?: RowProblems
  onClearServerProblems?: () => void
}

/**
 * One form step of the upload and edit dialogs (Details, Filing, Page ranges): the two flows collect the same things, so they
 * render the same steps. It reads the student's tags and syllabus and writes only into the draft.
 */
export function DocumentFormStep({
  step,
  draft,
  onDraft,
  form,
  pageCount,
  outline,
  serverProblems,
  onClearServerProblems,
}: DocumentFormStepProps) {
  const online = useOnline()
  const tags = useTags()
  const noteActions = useNoteActions()
  const { data, selection } = form

  if (step === 'details') {
    return (
      <DetailsStep
        value={draft}
        onChange={onDraft}
        tags={tags.data ?? []}
        onCreateTag={noteActions.addTag}
        online={online}
      />
    )
  }

  if (step === 'filing') {
    const summary =
      selection === null
        ? 'Unfiled'
        : selection
          ? linkLabel(linkFromSelection(selection))
          : 'Choose a chapter, or All chapters'
    return (
      <>
        {data.failed ? <Alert variant="error">We could not load your syllabus.</Alert> : null}
        <FilingStep
          state={draft.filing}
          onState={(change) => onDraft({ filing: pickerReduce(draft.filing, change) })}
          subjects={data.subjects}
          chapters={data.chapters}
          topics={data.topics}
          loadingSubjects={data.loadingSubjects}
          loadingChapters={data.loadingChapters}
          loadingTopics={data.loadingTopics}
          summary={summary}
        />
      </>
    )
  }

  return (
    <RangesStepContainer
      rows={draft.rows}
      onRows={(rows) => onDraft({ rows })}
      pageCount={pageCount}
      outline={outline}
      serverProblems={serverProblems}
      onClearServerProblems={onClearServerProblems}
    />
  )
}
