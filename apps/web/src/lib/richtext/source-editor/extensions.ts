import { defaultKeymap, history, historyKeymap, indentLess, indentMore } from '@codemirror/commands'
import { markdown, markdownLanguage } from '@codemirror/lang-markdown'
import { indentUnit, syntaxHighlighting } from '@codemirror/language'
import { EditorState, type Extension } from '@codemirror/state'
import { EditorView, keymap, placeholder as placeholderText } from '@codemirror/view'

import { backspaceCommand, enterCommand } from './enter'
import { createTabPolicy } from './tab-policy'
import { markdownHighlight, sourceTheme } from './theme'

export interface SourceExtensionOptions {
  label: string
  placeholder?: string
  readOnly?: boolean
  id?: string
  describedBy?: string
}

/**
 * Everything the Markdown box does, in one list. `markdown()` brings the behaviour students expect from a notes app:
 * Enter continues a list ("1." becomes "2.", bullets and "- [ ]" tasks carry on, quotes continue, Enter on an empty
 * item ends the list and leaves a blank line) and Backspace removes the marker. The text stays plain Markdown.
 */
export function sourceExtensions({
  label,
  placeholder,
  readOnly,
  id,
  describedBy,
}: SourceExtensionOptions): Extension[] {
  const tabs = createTabPolicy()
  const lineAtCaret = (view: EditorView) => view.state.doc.lineAt(view.state.selection.main.head).text
  const attributes: Record<string, string> = {
    'aria-label': label,
    'aria-multiline': 'true',
    spellcheck: 'true',
    autocapitalize: 'sentences',
  }
  if (id) attributes.id = id
  if (describedBy) attributes['aria-describedby'] = describedBy

  return [
    history(),
    // GFM flavour, so task items ("- [ ]") and tables are understood by the Enter handling.
    markdown({ base: markdownLanguage, addKeymap: false }),
    // Three spaces nest under both "- " and "1. ".
    indentUnit.of('   '),
    keymap.of([
      { key: 'Enter', run: enterCommand },
      { key: 'Backspace', run: backspaceCommand },
      {
        key: 'Escape',
        run: () => {
          tabs.release()
          return false
        },
      },
      { key: 'Tab', run: (view) => tabs.shouldIndent(lineAtCaret(view), false) && indentMore(view) },
      { key: 'Shift-Tab', run: (view) => tabs.shouldIndent(lineAtCaret(view), true) && indentLess(view) },
      ...defaultKeymap,
      ...historyKeymap,
    ]),
    EditorView.domEventHandlers({
      keydown: (event) => {
        if (!['Tab', 'Shift', 'Escape'].includes(event.key)) tabs.reset()
      },
      blur: () => tabs.reset(),
    }),
    EditorView.lineWrapping,
    syntaxHighlighting(markdownHighlight),
    sourceTheme,
    EditorView.contentAttributes.of(attributes),
    EditorState.readOnly.of(Boolean(readOnly)),
    // Some commands (list continuation) do not check the read-only flag themselves, so drop typed changes here.
    // Changes that come from the app (a reloaded value) carry no user event and still go through.
    EditorState.transactionFilter.of((tr) =>
      readOnly && tr.docChanged && (tr.isUserEvent('input') || tr.isUserEvent('delete')) ? [] : tr,
    ),
    EditorView.editable.of(!readOnly),
    ...(placeholder ? [placeholderText(placeholder)] : []),
  ]
}
