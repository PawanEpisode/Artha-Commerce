import { EditorState } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import { afterEach, beforeAll, describe, expect, it } from 'vitest'

import { sourceExtensions } from './extensions'

// jsdom has no layout; CodeMirror only asks for rectangles when it measures.
beforeAll(() => {
  const rect = { x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, toJSON: () => ({}) }
  Range.prototype.getClientRects = () => [] as unknown as DOMRectList
  Range.prototype.getBoundingClientRect = () => rect as DOMRect
})

let view: EditorView | undefined
afterEach(() => view?.destroy())

/** A real editor with the real extensions; `|` in `text` marks the caret. */
function open(text: string, readOnly = false) {
  const at = text.indexOf('|')
  const doc = text.replace('|', '')
  view = new EditorView({
    state: EditorState.create({
      doc,
      selection: { anchor: at },
      extensions: sourceExtensions({ label: 'Note text', readOnly }),
    }),
    parent: document.body,
  })
  return view
}

const press = (v: EditorView, key: string, init: KeyboardEventInit = {}) =>
  v.contentDOM.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...init }))

/** Document text with the caret shown as `|`. */
const shown = (v: EditorView) => {
  const head = v.state.selection.main.head
  const doc = v.state.doc.toString()
  return doc.slice(0, head) + '|' + doc.slice(head)
}

describe('Enter continues Markdown', () => {
  it('numbers the next item (the reported bug)', () => {
    const v = open('1. first|')
    press(v, 'Enter')
    expect(shown(v)).toBe('1. first\n2. |')
  })

  it('keeps counting', () => {
    const v = open('1. a\n2. b|')
    press(v, 'Enter')
    expect(shown(v)).toBe('1. a\n2. b\n3. |')
  })

  it('renumbers the items below when inserting in the middle', () => {
    const v = open('1. a|\n2. b')
    press(v, 'Enter')
    expect(v.state.doc.toString()).toBe('1. a\n2. \n3. b')
  })

  it('continues bullets and tasks, with the box unticked', () => {
    let v = open('- a|')
    press(v, 'Enter')
    expect(shown(v)).toBe('- a\n- |')
    v.destroy()
    v = open('- [x] done|')
    press(v, 'Enter')
    expect(shown(v)).toBe('- [x] done\n- [ ] |')
  })

  it('continues a quote', () => {
    const v = open('> note|')
    press(v, 'Enter')
    expect(shown(v)).toBe('> note\n> |')
  })

  it('Enter on an empty item ends the list and leaves a blank line so the next text is not part of the item', () => {
    const v = open('1. a\n2. b\n3. |')
    press(v, 'Enter')
    expect(shown(v)).toBe('1. a\n2. b\n\n|')
  })

  it('ends a bullet or task list the same way', () => {
    let v = open('- a\n- |')
    press(v, 'Enter')
    expect(shown(v)).toBe('- a\n\n|')
    v.destroy()
    v = open('- [ ] a\n- [ ] |')
    press(v, 'Enter')
    expect(v.state.selection.main.head).toBe(v.state.doc.length)
    expect(v.state.doc.toString()).not.toMatch(/- \[ \] $/)
  })

  it('keeps the parent marker when ending a nested list (no blank line)', () => {
    const v = open('- a\n   - b\n   - |')
    press(v, 'Enter')
    expect(v.state.doc.toString()).not.toContain('\n\n')
  })

  it('Backspace right after a marker removes the marker in two steps', () => {
    const v = open('- a\n- |')
    press(v, 'Backspace')
    // The first Backspace turns the marker into indentation, the second removes it (CodeMirror's own behaviour).
    expect(v.state.doc.toString()).toBe('- a\n  ')
    press(v, 'Backspace')
    expect(v.state.doc.toString()).toBe('- a\n')
  })

  it('leaves ordinary paragraphs alone', () => {
    const v = open('plain text|')
    press(v, 'Enter')
    expect(v.state.doc.toString()).toBe('plain text\n')
  })

  it('does nothing when read-only', () => {
    const v = open('1. first|', true)
    press(v, 'Enter')
    expect(v.state.doc.toString()).toBe('1. first')
  })
})

describe('Tab in lists', () => {
  it('indents a list item and outdents it again', () => {
    const v = open('- a\n- b|')
    press(v, 'Tab')
    expect(v.state.doc.toString()).toBe('- a\n   - b')
    press(v, 'Tab', { shiftKey: true })
    expect(v.state.doc.toString()).toBe('- a\n- b')
  })

  it('is not swallowed outside a list', () => {
    const v = open('plain|')
    const notPrevented = press(v, 'Tab')
    expect(v.state.doc.toString()).toBe('plain')
    expect(notPrevented).toBe(true)
  })

  it('Escape then Tab leaves the box even inside a list', () => {
    const v = open('- a|')
    press(v, 'Escape')
    const notPrevented = press(v, 'Tab')
    expect(v.state.doc.toString()).toBe('- a')
    expect(notPrevented).toBe(true)
  })
})
