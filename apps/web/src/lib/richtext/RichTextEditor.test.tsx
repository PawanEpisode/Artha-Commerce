import { EditorView } from '@codemirror/view'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { beforeAll, describe, expect, it, vi } from 'vitest'

import { type PickedImage, RichTextEditor } from './RichTextEditor'

beforeAll(() => {
  const rect = { x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, toJSON: () => ({}) }
  Range.prototype.getClientRects = () => [] as unknown as DOMRectList
  Range.prototype.getBoundingClientRect = () => rect as DOMRect
})

function Harness({
  initial,
  onValue,
  ...rest
}: {
  initial: string
  onValue?: (v: string) => void
  readOnly?: boolean
  onPickImage?: () => Promise<PickedImage | null>
}) {
  const [value, setValue] = useState(initial)
  return (
    <RichTextEditor
      value={value}
      onChange={(v) => {
        setValue(v)
        onValue?.(v)
      }}
      label="Note text"
      {...rest}
    />
  )
}

/** The lazy CodeMirror box takes a moment to load; resolves with its view. */
async function editor() {
  // The first test pays for the dynamic import; the 1 s default is too tight (vitest fails a test at 5 s) when the whole suite runs in parallel.
  await waitFor(() => expect(document.querySelector('.cm-content')).not.toBeNull(), { timeout: 4_000 })
  return EditorView.findFromDOM(document.querySelector<HTMLElement>('.cm-editor')!)!
}

const press = (view: EditorView, key: string) =>
  view.contentDOM.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }))

describe('RichTextEditor', () => {
  it('names the box for screen readers and keeps the app value in sync', async () => {
    render(<Harness initial="hello" />)
    const view = await editor()
    expect(view.contentDOM).toHaveAttribute('aria-label', 'Note text')
    expect(view.contentDOM).toHaveAttribute('aria-multiline', 'true')
    expect(view.state.doc.toString()).toBe('hello')
  })

  it('Numbered list button turns the line into "1. first" and puts the caret after it', async () => {
    const seen = vi.fn()
    render(<Harness initial="first" onValue={seen} />)
    const view = await editor()
    await userEvent.click(screen.getByRole('button', { name: 'Numbered list' }))
    expect(seen).toHaveBeenLastCalledWith('1. first')
    expect(view.state.doc.toString()).toBe('1. first')
  })

  it('Enter after a numbered item adds "2." and the preview shows both items', async () => {
    const seen = vi.fn()
    render(<Harness initial="1. first" onValue={seen} />)
    const view = await editor()
    view.dispatch({ selection: { anchor: view.state.doc.length } })
    press(view, 'Enter')
    expect(seen).toHaveBeenLastCalledWith('1. first\n2. ')
    view.dispatch({ changes: { from: view.state.doc.length, insert: 'second' } })
    await waitFor(() => {
      const items = document.querySelectorAll('section[aria-label="Preview"] ol > li')
      expect(Array.from(items).map((li) => li.textContent)).toEqual(['first', 'second'])
    })
  })

  it('shows a single Enter in a paragraph as a line break in the preview', async () => {
    render(<Harness initial={'line one\nline two'} />)
    await editor()
    await waitFor(() => expect(document.querySelector('section[aria-label="Preview"] br')).not.toBeNull())
  })

  it('inserts a picked image at the caret that was there before the dialog opened', async () => {
    const seen = vi.fn()
    const pick = vi.fn().mockResolvedValue({ attachmentId: '3f2b8c1e-5a4d-4e9b-8c7a-1d2e3f4a5b6c', alt: 'Chart' })
    render(<Harness initial={'before after'} onValue={seen} onPickImage={pick} />)
    const view = await editor()
    view.dispatch({ selection: { anchor: 7 } })
    await userEvent.click(screen.getByRole('button', { name: 'Add image' }))
    await waitFor(() => expect(seen).toHaveBeenCalled())
    expect(view.state.doc.toString()).toContain('![Chart](attachment:3f2b8c1e-5a4d-4e9b-8c7a-1d2e3f4a5b6c)')
    expect(view.state.doc.toString().startsWith('before ')).toBe(true)
  })

  it('shows text the app replaces (a restored draft) without reporting it as an edit', async () => {
    const onChange = vi.fn()
    const { rerender } = render(<RichTextEditor value="old" onChange={onChange} label="Note text" />)
    const view = await editor()
    rerender(<RichTextEditor value={'restored\n- item'} onChange={onChange} label="Note text" />)
    await waitFor(() => expect(view.state.doc.toString()).toBe('restored\n- item'))
    expect(onChange).not.toHaveBeenCalled()
  })

  it('read-only hides the toolbar and refuses edits', async () => {
    render(<Harness initial="1. first" readOnly />)
    const view = await editor()
    expect(screen.queryByRole('toolbar')).not.toBeInTheDocument()
    view.dispatch({ selection: { anchor: view.state.doc.length } })
    press(view, 'Enter')
    expect(view.state.doc.toString()).toBe('1. first')
  })
})
