import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ChapterPickerSheet } from './ChapterPickerSheet'

const props = {
  currentLabel: 'Unfiled',
  open: true,
  onOpenChange: () => undefined,
  state: { subjectId: '', chapterId: '', topicId: '' },
  onState: () => undefined,
  subjects: [{ id: 's1', key: 'taxation', name: 'Taxation' }],
  chapters: [],
  topics: [],
  loadingSubjects: false,
  loadingChapters: false,
  loadingTopics: false,
  failed: false,
  onRetry: () => undefined,
  canApply: false,
  onApply: () => undefined,
}

describe('ChapterPickerSheet', () => {
  it('shows where the note is filed on the button', () => {
    render(<ChapterPickerSheet {...props} open={false} currentLabel="Taxation › GST" />)
    expect(screen.getByRole('button', { name: /Filed under:\s*Taxation › GST/ })).toBeInTheDocument()
  })

  it('keeps the chapter list off until a subject is chosen, and Apply off until a chapter is chosen', () => {
    render(<ChapterPickerSheet {...props} />)
    expect(screen.getByRole('dialog')).toHaveTextContent('File this note')
    expect(screen.getByLabelText('Chapter')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'File here' })).toBeDisabled()
  })

  it('shows the topic list only inside a chapter, and applies', async () => {
    const onApply = vi.fn()
    render(
      <ChapterPickerSheet
        {...props}
        state={{ subjectId: 's1', chapterId: 'c1', topicId: '' }}
        chapters={[{ id: 'c1', key: 'itc', name: 'ITC' }]}
        topics={[{ id: 't1', key: 'blocked', name: 'Blocked credits' }]}
        canApply
        onApply={onApply}
      />,
    )
    expect(screen.getByLabelText('Topic (optional)')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'File here' }))
    expect(onApply).toHaveBeenCalled()
  })

  it('offers to move a filed note to Unfiled', async () => {
    const onClear = vi.fn()
    render(<ChapterPickerSheet {...props} onClear={onClear} />)
    await userEvent.click(screen.getByRole('button', { name: 'Move to Unfiled' }))
    expect(onClear).toHaveBeenCalled()
  })

  it('shows a loading state and an error with retry', async () => {
    const onRetry = vi.fn()
    const { rerender } = render(<ChapterPickerSheet {...props} loadingSubjects />)
    expect(screen.queryByLabelText('Subject')).toBeNull()
    rerender(<ChapterPickerSheet {...props} failed onRetry={onRetry} />)
    expect(screen.getByText('We could not load your syllabus.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalled()
  })
})
