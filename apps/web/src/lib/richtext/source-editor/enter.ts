import { deleteMarkupBackward, insertNewlineContinueMarkupCommand } from '@codemirror/lang-markdown'
import type { Command } from '@codemirror/view'

/**
 * CodeMirror's default turns a two-item list with an empty second item into a spaced-out list instead of ending it.
 * Students expect Enter on an empty item to end the list every time.
 */
const continueMarkup = insertNewlineContinueMarkupCommand({ nonTightLists: false })

/** A list line with a marker and nothing after it: "1. ", "- ", "- [ ] ". */
const EMPTY_ITEM = /^\s*(?:[-*+]|\d+[.)])\s*(?:\[[ xX]\]\s*)?$/

/**
 * Enter in Markdown. The list, task and quote continuation is CodeMirror's own (`insertNewlineContinueMarkupCommand`: "1."
 * becomes "2.", Enter on an empty item ends the list). One addition: when Enter ends a list, a blank line is left
 * behind. Without it the next thing typed sits directly under the last item, and Markdown treats it as part of that
 * item (the preview shows it indented inside the list).
 */
export const enterCommand: Command = (view) => {
  const { state } = view
  const caret = state.selection.main
  const line = state.doc.lineAt(caret.head)
  const endsList =
    caret.empty && EMPTY_ITEM.test(line.text) && line.number > 1 && state.doc.line(line.number - 1).text.trim() !== ''

  if (!continueMarkup(view)) return false
  if (!endsList) return true

  const now = view.state.doc.lineAt(view.state.selection.main.head)
  if (now.text === '') {
    view.dispatch({
      changes: { from: now.from, insert: '\n' },
      selection: { anchor: now.from + 1 },
      userEvent: 'input',
    })
  }
  return true
}

/** Backspace right after a list or quote marker removes the marker (CodeMirror's own command). */
export const backspaceCommand: Command = deleteMarkupBackward
