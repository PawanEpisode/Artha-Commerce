import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { makeNote } from '../lib/testing'
import type { ChapterSuggestion } from '../lib/types'
import { ChapterNotesCard } from './ChapterNotesCard'
import { ChapterRows } from './ChapterRows'
import { DeleteNotesDialog, isDeleteConfirmed } from './DeleteNotesDialog'
import { sectionOf } from './NotesNav'
import { RecentSearches, SearchHitList } from './SearchParts'
import { SubjectGrid } from './SubjectGrid'
import { SuggestionBar } from './SuggestionBar'
import { TrashList } from './TrashList'
import { UsageSection } from './UsageSection'

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)

const suggestion = (id: string, chapter: string): ChapterSuggestion => ({
  chapter_id: id,
  chapter_key: id,
  chapter_name: chapter,
  subject_id: 's',
  subject_key: 'tax',
  subject_name: 'Taxation',
  score: 1,
})

describe('SuggestionBar', () => {
  it('files with one tap on a suggestion, or opens the full picker', async () => {
    const onPick = vi.fn()
    const onOther = vi.fn()
    render(<SuggestionBar suggestions={[suggestion('c1', 'ITC')]} onPick={onPick} onOther={onOther} />)
    await userEvent.click(screen.getByRole('button', { name: /ITC/ }))
    expect(onPick).toHaveBeenCalledWith(expect.objectContaining({ chapter_id: 'c1' }))
    await userEvent.click(screen.getByRole('button', { name: 'Choose a chapter' }))
    expect(onOther).toHaveBeenCalled()
  })

  it('still offers the picker with no suggestions', () => {
    render(<SuggestionBar suggestions={[]} onPick={() => undefined} onOther={() => undefined} />)
    expect(screen.getByRole('button', { name: 'Choose a chapter' })).toBeInTheDocument()
    expect(screen.queryByText('Looks like')).toBeNull()
  })
})

describe('TrashList', () => {
  const note = makeNote({ title: 'Old', deleted_at: '2026-10-01T00:00:00Z', purge_after: '2099-01-01T00:00:00Z' })
  it('says how long a note is kept and restores it', async () => {
    const onRestore = vi.fn()
    render(<TrashList items={[note]} online onRestore={onRestore} />)
    expect(screen.getByText(/Removed for good in/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Restore Old' }))
    expect(onRestore).toHaveBeenCalledWith(note)
  })
  it('cannot restore offline', () => {
    render(<TrashList items={[note]} online={false} onRestore={() => undefined} />)
    expect(screen.getByRole('button', { name: 'Restore Old' })).toBeDisabled()
  })
})

describe('UsageSection', () => {
  const usage = {
    plan: 'free',
    limits: { max_storage_mb: 500, max_notes: 2000, max_note_chars: 100000, max_note_images: 40, max_tags: 200 },
    used: { storage_bytes: 100 * 1024 * 1024, notes: 1900, tags: 3 },
    resets_on: '2026-11-01',
  }
  it('shows the three meters with numbers in text, and the export and delete actions', async () => {
    const onExport = vi.fn()
    const onDeleteAll = vi.fn()
    render(<UsageSection usage={usage} exporting={false} onExport={onExport} onDeleteAll={onDeleteAll} />)
    expect(screen.getAllByRole('meter')).toHaveLength(3)
    await userEvent.click(screen.getByRole('button', { name: /Export all my notes/ }))
    await userEvent.click(screen.getByRole('button', { name: /Delete all my notes/ }))
    expect(onExport).toHaveBeenCalled()
    expect(onDeleteAll).toHaveBeenCalled()
  })
  it('still offers export and delete when the numbers are not available', () => {
    render(<UsageSection exporting onExport={() => undefined} onDeleteAll={() => undefined} />)
    expect(screen.queryByRole('meter')).toBeNull()
    expect(screen.getByRole('button', { name: /Preparing/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Delete all my notes/ })).toBeEnabled()
  })
})

describe('DeleteNotesDialog', () => {
  it('only deletes after the word is typed', async () => {
    const onConfirm = vi.fn()
    render(
      <DeleteNotesDialog open onOpenChange={() => undefined} pending={false} failed={false} onConfirm={onConfirm} />,
    )
    const button = screen.getByRole('button', { name: 'Delete everything' })
    expect(button).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Type DELETE to confirm'), 'delete')
    expect(button).toBeEnabled()
    await userEvent.click(button)
    expect(onConfirm).toHaveBeenCalled()
    expect(isDeleteConfirmed(' Delete ')).toBe(true)
    expect(isDeleteConfirmed('del')).toBe(false)
  })
  it('shows a failure in words', () => {
    render(<DeleteNotesDialog open onOpenChange={() => undefined} pending={false} failed onConfirm={() => undefined} />)
    expect(screen.getByText(/We could not delete your notes/)).toBeInTheDocument()
  })
})

describe('SubjectGrid and ChapterRows', () => {
  it('never shows zero for a count that failed to load', () => {
    render(
      <SubjectGrid
        subjects={[
          { key: 'a', name: 'Audit', notes: 3, state: 'ok' },
          { key: 'b', name: 'Law', state: 'error' },
          { key: 'c', name: 'Tax', state: 'loading' },
        ]}
      />,
    )
    expect(screen.getByRole('link', { name: 'Audit' })).toHaveAttribute('href', '/app/notes/a')
    expect(screen.getByText('3 notes')).toBeInTheDocument()
    expect(screen.getByText('Count not available')).toBeInTheDocument()
  })

  it('lists chapters with their counts and re-links a moved one', async () => {
    const onRelink = vi.fn()
    const moved = { chapter_key: 'old', chapter_name: 'Old chapter', notes: 2, highlights: 0, marks: 0, documents: 0 }
    render(
      <ChapterRows
        subjectKey="tax"
        chapters={[
          {
            chapter_id: 'c1',
            chapter_key: 'itc',
            name: 'ITC',
            notes: 1,
            highlights: 0,
            marks: 0,
            documents: 0,
            has_summary: true,
            last_noted_at: '2026-10-01T00:00:00Z',
          },
        ]}
        moved={[moved]}
        onRelink={onRelink}
      />,
    )
    expect(screen.getByRole('link', { name: 'ITC' })).toHaveAttribute('href', '/app/notes/tax/itc')
    expect(screen.getByText('Has summary')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Re-link' }))
    expect(onRelink).toHaveBeenCalledWith(moved)
  })
})

describe('search parts', () => {
  it('highlights the matching words with mark', () => {
    render(
      <SearchHitList
        query="credit"
        hits={[
          {
            type: 'note',
            id: 'x',
            title: 'Input credit',
            snippet: 'credit is blocked',
            link: makeNote().link,
            rank: 1,
            updated_at: '2026-10-01T00:00:00Z',
          },
        ]}
      />,
    )
    expect(document.querySelectorAll('mark')).toHaveLength(2)
    expect(screen.getByRole('link')).toHaveAttribute('href', '/app/notes/n/x')
  })
  it('lists recent searches and clears them', async () => {
    const onPick = vi.fn()
    const onClear = vi.fn()
    render(<RecentSearches items={['17(5)', 'ITC']} onPick={onPick} onClear={onClear} />)
    await userEvent.click(screen.getByRole('button', { name: /17\(5\)/ }))
    expect(onPick).toHaveBeenCalledWith('17(5)')
    await userEvent.click(screen.getByRole('button', { name: /Clear/ }))
    expect(onClear).toHaveBeenCalled()
  })
})

describe('ChapterNotesCard', () => {
  const overview = {
    chapter: { id: 'c', key: 'itc', name: 'ITC', subject_key: 'tax', subject_name: 'Taxation', level_id: 'l' },
    counts: { notes: 3, highlights: 0, marks: 0, documents: 0 },
    has_summary: false,
    last_noted_at: '2026-10-01T00:00:00Z',
    current_summary: null,
    recent: [makeNote({ title: 'Blocked credits' })],
    documents: [],
  }
  it('shows counts, the exam summary status, and links that carry stable keys', () => {
    render(
      <ChapterNotesCard
        state="ready"
        overview={overview}
        subjectKey="tax"
        chapterKey="itc"
        levelId="l"
        onRetry={() => undefined}
      />,
    )
    expect(screen.getByText(/3 notes in this chapter/)).toBeInTheDocument()
    expect(screen.getByText('Exam summary: not written yet.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open notes' })).toHaveAttribute('href', '/app/notes/tax/itc')
    expect(screen.getByRole('link', { name: /New note/ }).getAttribute('href')).toContain('/app/notes/new?')
  })
  it('has loading and error states', async () => {
    const onRetry = vi.fn()
    const { rerender } = render(
      <ChapterNotesCard state="loading" subjectKey="tax" chapterKey="itc" onRetry={onRetry} />,
    )
    expect(screen.queryByRole('link')).toBeNull()
    rerender(<ChapterNotesCard state="error" subjectKey="tax" chapterKey="itc" onRetry={onRetry} />)
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalled()
  })
  it('says when the chapter has no notes yet', () => {
    render(
      <ChapterNotesCard
        state="ready"
        overview={{ ...overview, counts: { ...overview.counts, notes: 0 }, recent: [] }}
        subjectKey="tax"
        chapterKey="itc"
        onRetry={() => undefined}
      />,
    )
    expect(screen.getByText('You have no notes in this chapter yet.')).toBeInTheDocument()
  })
})

describe('sectionOf', () => {
  it('maps paths to tabs', () => {
    expect(sectionOf('/app/notes')).toBe('notes')
    expect(sectionOf('/app/notes/taxation/itc')).toBe('notes')
    expect(sectionOf('/app/notes/search')).toBe('search')
    expect(sectionOf('/app/notes/trash')).toBe('trash')
    expect(sectionOf('/app/settings/notes')).toBe('settings')
  })
})
