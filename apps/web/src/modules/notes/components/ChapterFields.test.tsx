import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ALL_CHAPTERS } from '~/modules/coverage'

import { ChapterFields, type ChapterFieldsProps } from './ChapterFields'

const props: ChapterFieldsProps = {
  idPrefix: 't',
  state: { subjectId: '', chapterId: '', topicId: '' },
  onState: () => undefined,
  subjects: [{ id: 's1', key: 'tax', name: 'Taxation' }],
  chapters: [{ id: 'c1', key: 'itc', name: 'ITC' }],
  topics: [{ id: 't1', key: 'blocked', name: 'Blocked credits' }],
  allowAll: true,
}

const withSubject = { subjectId: 's1', chapterId: '', topicId: '' }

describe('ChapterFields', () => {
  it('disables Chapter until a subject is chosen, with no All chapters yet', () => {
    render(<ChapterFields {...props} />)
    expect(screen.getByLabelText('Chapter')).toBeDisabled()
    expect(screen.queryByRole('option', { name: 'All chapters' })).not.toBeInTheDocument()
  })

  it('offers All chapters once a subject is chosen and allowAll is on', async () => {
    render(<ChapterFields {...props} state={withSubject} />)
    await userEvent.click(screen.getByLabelText('Chapter'))
    expect(screen.getByRole('option', { name: 'All chapters' })).toBeInTheDocument()
  })

  it('leaves All chapters out when allowAll is off', async () => {
    render(<ChapterFields {...props} state={withSubject} allowAll={false} />)
    await userEvent.click(screen.getByLabelText('Chapter'))
    expect(await screen.findByRole('option', { name: 'ITC' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'All chapters' })).not.toBeInTheDocument()
  })

  it('shows Topic only for a real chapter', () => {
    const { rerender } = render(<ChapterFields {...props} state={{ ...withSubject, chapterId: ALL_CHAPTERS }} />)
    expect(screen.queryByLabelText('Topic (optional)')).not.toBeInTheDocument()
    rerender(<ChapterFields {...props} state={{ ...withSubject, chapterId: 'c1' }} />)
    expect(screen.getByLabelText('Topic (optional)')).toBeInTheDocument()
  })
})
