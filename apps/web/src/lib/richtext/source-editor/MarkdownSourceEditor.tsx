import { Annotation, Compartment, EditorState, Transaction } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import { type Ref, useEffect, useImperativeHandle, useLayoutEffect, useMemo, useRef } from 'react'

import type { Edit } from '../edit-actions'
import { minimalChange } from './diff'
import { sourceExtensions } from './extensions'

export interface Selection {
  start: number
  end: number
}

/** What the toolbar needs from the box: where the selection is, and a way to run a pure text edit on it. */
export interface SourceEditorHandle {
  focus: () => void
  selection: () => Selection
  /** Runs a toolbar edit on the current selection (or on `at`, for an edit that waited on a dialog). */
  apply: (action: (edit: Edit) => Edit, at?: Selection) => void
}

export interface MarkdownSourceEditorProps {
  value: string
  onChange: (value: string) => void
  label: string
  placeholder?: string
  readOnly?: boolean
  id?: string
  describedBy?: string
  ref?: Ref<SourceEditorHandle>
}

/** Marks a change that came from the app (a reloaded value), so it is not echoed back through `onChange`. */
const fromApp = Annotation.define<boolean>()

/**
 * The Markdown text box, built directly on CodeMirror 6 (no wrapper: the wrapper pulls in autocomplete and a default
 * theme we do not use, which more than doubles the download). Loaded lazily by `RichTextEditor`. The value stays plain
 * Markdown in and out; CodeMirror only adds the editing behaviour.
 */
export default function MarkdownSourceEditor({
  value,
  onChange,
  label,
  placeholder,
  readOnly = false,
  id,
  describedBy,
  ref,
}: MarkdownSourceEditorProps) {
  const host = useRef<HTMLDivElement>(null)
  const view = useRef<EditorView | null>(null)
  const latest = useRef({ value, onChange })
  const config = useRef(new Compartment())
  const extensions = useMemo(
    () => sourceExtensions({ label, placeholder, readOnly, id, describedBy }),
    [label, placeholder, readOnly, id, describedBy],
  )

  useLayoutEffect(() => {
    latest.current = { value, onChange }
  })

  // Create the view once. Later changes to labels or read-only reconfigure it in place, keeping caret and undo history.
  useEffect(() => {
    if (!host.current) return
    const editor = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: latest.current.value,
        extensions: [
          config.current.of(extensions),
          EditorView.updateListener.of((update) => {
            if (!update.docChanged || update.transactions.some((tr) => tr.annotation(fromApp))) return
            latest.current.onChange(update.state.doc.toString())
          }),
        ],
      }),
    })
    view.current = editor
    return () => {
      editor.destroy()
      view.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- created once; `extensions` is applied by the effect below
  }, [])

  useEffect(() => {
    view.current?.dispatch({ effects: config.current.reconfigure(extensions) })
  }, [extensions])

  // The app changed the text (draft restored, note reloaded): apply only what differs, and do not make it undoable.
  useEffect(() => {
    const editor = view.current
    if (!editor) return
    const change = minimalChange(editor.state.doc.toString(), value)
    if (change)
      editor.dispatch({ changes: change, annotations: [fromApp.of(true), Transaction.addToHistory.of(false)] })
  }, [value])

  useImperativeHandle(
    ref,
    () => ({
      focus: () => view.current?.focus(),
      selection: () => {
        const range = view.current?.state.selection.main
        return { start: range?.from ?? 0, end: range?.to ?? 0 }
      },
      apply: (action, at) => {
        const editor = view.current
        if (!editor || readOnly) return
        const main = editor.state.selection.main
        const prev = editor.state.doc.toString()
        const next = action({ value: prev, start: at?.start ?? main.from, end: at?.end ?? main.to })
        const change = minimalChange(prev, next.value)
        const clamp = (n: number) => Math.max(0, Math.min(n, next.value.length))
        editor.dispatch({
          ...(change ? { changes: change } : {}),
          selection: { anchor: clamp(next.start), head: clamp(next.end) },
          scrollIntoView: true,
          userEvent: 'input',
        })
        editor.focus()
      },
    }),
    [readOnly],
  )

  return <div ref={host} data-slot="markdown-source-editor" />
}
