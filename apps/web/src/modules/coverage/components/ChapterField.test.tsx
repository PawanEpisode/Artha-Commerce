import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ChapterField } from './ChapterField'

const chapters = [
  { id: 'c1', name: 'Chapter One' },
  { id: 'c2', name: 'Chapter Two' },
]

describe('ChapterField', () => {
  it('offers "All chapters" before the chapters, and reports the whole subject as no chapter id', async () => {
    const onChange = vi.fn()
    render(
      <ChapterField
        id="ch"
        chapters={chapters}
        value={{ chapter_id: null, all_chapters: false }}
        unsetLabel="No chapter"
        onChange={onChange}
      />,
    )
    await userEvent.click(screen.getByRole('combobox', { name: 'Chapter' }))
    const options = (await screen.findAllByRole('option')).map((o) => o.textContent)
    expect(options).toEqual(['No chapter', 'All chapters', 'Chapter One', 'Chapter Two'])
    await userEvent.click(screen.getByRole('option', { name: 'All chapters' }))
    expect(onChange).toHaveBeenCalledWith({ chapter_id: null, all_chapters: true })
  })

  it('shows "All chapters" for the whole subject and drops the unset choice once something is chosen', async () => {
    render(
      <ChapterField
        id="ch"
        chapters={chapters}
        value={{ chapter_id: null, all_chapters: true }}
        unsetLabel="No chapter"
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByRole('combobox', { name: 'Chapter' })).toHaveTextContent('All chapters')
    await userEvent.click(screen.getByRole('combobox', { name: 'Chapter' }))
    expect(screen.queryByRole('option', { name: 'No chapter' })).toBeNull()
  })

  it('reports a single chapter by id', async () => {
    const onChange = vi.fn()
    render(
      <ChapterField id="ch" chapters={chapters} value={{ chapter_id: null, all_chapters: true }} onChange={onChange} />,
    )
    await userEvent.click(screen.getByRole('combobox', { name: 'Chapter' }))
    await userEvent.click(await screen.findByRole('option', { name: 'Chapter Two' }))
    expect(onChange).toHaveBeenCalledWith({ chapter_id: 'c2', all_chapters: false })
  })
})
