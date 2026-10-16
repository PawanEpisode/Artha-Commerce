import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { FILED_LINK, makeNote } from '../lib/testing'
import { NoteRow } from './NoteRow'

const inTable = {
  wrapper: ({ children }: { children: React.ReactNode }) => (
    <table>
      <tbody>{children}</tbody>
    </table>
  ),
}

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)

describe('NoteRow', () => {
  it('links the title to the note and shows the snippet and where it is filed', () => {
    render(<NoteRow note={makeNote({ link: FILED_LINK, title: 'Blocked credits' })} />, inTable)
    expect(screen.getByRole('link', { name: 'Blocked credits' })).toHaveAttribute(
      'href',
      '/app/notes/n/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    )
    expect(screen.getByText('ITC is blocked for motor vehicles.')).toBeInTheDocument()
    const location = screen.getByText('GST: Input tax credit')
    expect(location).toBeInTheDocument()
    expect(location.closest('[title]')).toHaveAttribute('title', 'Taxation › GST: Input tax credit')
    expect(location).toHaveClass('truncate')
  })

  it('says Unfiled for a note with no chapter, and Untitled for an empty title', () => {
    render(<NoteRow note={makeNote({ title: '  ' })} />, inTable)
    expect(screen.getByText('Unfiled')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Untitled note' })).toBeInTheDocument()
  })

  it('names the offline copy and the tags in words', () => {
    render(
      <NoteRow note={makeNote({ offline_copy: true, tags: [{ id: 't1', name: 'doubt', color_key: null }] })} />,
      inTable,
    )
    expect(screen.getByText('Offline copy')).toBeInTheDocument()
    expect(screen.getByText('doubt')).toBeInTheDocument()
  })

  it('pins and trashes through buttons with compact buttons and clear names', async () => {
    const onPin = vi.fn()
    const onTrash = vi.fn()
    render(<NoteRow note={makeNote({ title: 'Cash flow' })} onPin={onPin} onTrash={onTrash} />, inTable)
    const pin = screen.getByRole('button', { name: 'Pin Cash flow' })
    expect(pin).toHaveClass('size-7')
    await userEvent.click(pin)
    expect(onPin).toHaveBeenCalledWith(true)
    await userEvent.click(screen.getByRole('button', { name: 'Move Cash flow to Trash' }))
    expect(onTrash).toHaveBeenCalled()
  })

  it('offers Unpin on a pinned note and can hide the location line', () => {
    render(
      <NoteRow
        note={makeNote({ pinned: true, title: 'Pinned one', link: FILED_LINK })}
        onPin={vi.fn()}
        showLocation={false}
      />,
      inTable,
    )
    expect(screen.getByRole('button', { name: 'Unpin Pinned one' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByText('Taxation › GST: Input tax credit')).toBeNull()
  })
})
