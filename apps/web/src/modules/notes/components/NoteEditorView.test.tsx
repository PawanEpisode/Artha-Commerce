import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { NoteEditorView } from './NoteEditorView'

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)

const base = {
  title: 'GST',
  onTitle: () => undefined,
  body: 'Hello',
  onBody: () => undefined,
  localOnly: false,
  sync: { state: 'saved' as const, count: 0 },
  recovered: false,
  onDiscardRecovered: () => undefined,
  problems: null,
  saveFailed: false,
  overBy: 0,
  maxChars: 100_000,
  online: true,
  onSave: () => undefined,
  onPickImage: async () => null,
  linkControl: <button>Filed under Unfiled</button>,
  tagsControl: <p>tags here</p>,
}

describe('NoteEditorView', () => {
  it('says Saved, Saving, Offline with a count, and Needs attention, as text', () => {
    const { rerender } = render(<NoteEditorView {...base} />)
    expect(screen.getByText('Saved')).toBeInTheDocument()
    rerender(<NoteEditorView {...base} sync={{ state: 'saving', count: 0 }} />)
    expect(screen.getByText('Saving…')).toBeInTheDocument()
    rerender(<NoteEditorView {...base} sync={{ state: 'offline', count: 2 }} />)
    expect(screen.getByText('Offline: saved on this device, 2 waiting')).toBeInTheDocument()
    rerender(<NoteEditorView {...base} sync={{ state: 'attention', count: 1 }} />)
    expect(screen.getByText('1 needs your attention')).toBeInTheDocument()
  })

  it('opens the conflict sheet from the status chip', async () => {
    const onSyncPress = vi.fn()
    render(<NoteEditorView {...base} sync={{ state: 'attention', count: 1 }} onSyncPress={onSyncPress} />)
    await userEvent.click(screen.getByRole('button', { name: /needs your attention/ }))
    expect(onSyncPress).toHaveBeenCalled()
  })

  it('shows a recovered draft with a way to discard it', async () => {
    const onDiscard = vi.fn()
    render(<NoteEditorView {...base} recovered onDiscardRecovered={onDiscard} />)
    expect(screen.getByText('Recovered draft.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Discard draft' }))
    expect(onDiscard).toHaveBeenCalled()
  })

  it('reports being over the limit and blocks the save button', () => {
    render(<NoteEditorView {...base} overBy={1200} />)
    expect(screen.getByText(/1,200 characters over the 1,00,000 character limit/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save now' })).toBeDisabled()
  })

  it('lists the lint problems and keeps the text safe', () => {
    render(
      <NoteEditorView
        {...base}
        problems={{
          kind: 'lint',
          issues: [{ code: 'x', message: 'Links must start with https.', line: 3, severity: 'error' }],
        }}
      />,
    )
    expect(screen.getByText(/Your text is kept on this device/)).toBeInTheDocument()
    expect(screen.getByText('Line 3: Links must start with https.')).toBeInTheDocument()
  })

  it('says a note that only exists on this device waits to sync, and that images need a connection offline', () => {
    render(<NoteEditorView {...base} localOnly savedText="Saved 4:30 pm" online={false} />)
    expect(screen.getByText('Saved on this device, waiting to sync')).toBeInTheDocument()
    expect(screen.queryByText('Saved 4:30 pm')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save now' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /image/i })).toBeDisabled()
  })

  it('shows the last saved time once the note is known to the server', () => {
    render(<NoteEditorView {...base} savedText="Saved 4:30 pm" />)
    expect(screen.getByText('Saved 4:30 pm')).toBeInTheDocument()
    expect(screen.queryByText(/waiting to sync/)).not.toBeInTheDocument()
  })

  it('edits the title through its label and pins, shows history and trash when allowed', async () => {
    const onTitle = vi.fn()
    const onPin = vi.fn()
    const onHistory = vi.fn()
    const onTrash = vi.fn()
    render(
      <NoteEditorView
        {...base}
        onTitle={onTitle}
        onPin={onPin}
        onHistory={onHistory}
        onTrash={onTrash}
        pinned={false}
      />,
    )
    await userEvent.type(screen.getByLabelText('Title'), '!')
    expect(onTitle).toHaveBeenCalledWith('GST!')
    await userEvent.click(screen.getByRole('button', { name: 'Pin' }))
    await userEvent.click(screen.getByRole('button', { name: 'History' }))
    await userEvent.click(screen.getByRole('button', { name: 'Move to Trash' }))
    expect([onPin, onHistory, onTrash].every((f) => f.mock.calls.length === 1)).toBe(true)
  })

  it('is read only for a trashed note', () => {
    render(<NoteEditorView {...base} readOnly />)
    expect(screen.getByLabelText('Title')).toHaveAttribute('readonly')
    expect(screen.getByRole('button', { name: 'Save now' })).toBeDisabled()
  })
})
