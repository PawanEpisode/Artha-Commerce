import { HighlightStyle } from '@codemirror/language'
import { EditorView } from '@codemirror/view'
import { tags as t } from '@lezer/highlight'

/**
 * The editor's look, written only with design tokens (CSS variables) so it follows all four themes. Colours are limited
 * to pairs `check:contrast` already covers on `card`: foreground, muted-foreground and primary.
 */
export const sourceTheme = EditorView.theme({
  '&': { color: 'var(--foreground)', backgroundColor: 'transparent', fontSize: 'inherit' },
  '&.cm-focused': { outline: 'none' },
  '.cm-scroller': { fontFamily: 'inherit', lineHeight: 'inherit', minHeight: '45dvh', overflow: 'auto' },
  '.cm-content': { padding: '0.625rem 0.875rem', caretColor: 'var(--foreground)' },
  '.cm-line': { padding: '0' },
  '.cm-placeholder': { color: 'var(--muted-foreground)' },
})

export const markdownHighlight = HighlightStyle.define([
  { tag: [t.heading1, t.heading2, t.heading3, t.heading4, t.heading5, t.heading6], fontWeight: '700' },
  { tag: t.strong, fontWeight: '700' },
  { tag: t.emphasis, fontStyle: 'italic' },
  { tag: t.strikethrough, textDecoration: 'line-through' },
  { tag: [t.link, t.url], color: 'var(--primary)' },
  // The punctuation that makes the formatting (#, **, -, 1., >) steps back so the words read first.
  { tag: [t.processingInstruction, t.contentSeparator, t.meta], color: 'var(--muted-foreground)' },
  { tag: t.quote, color: 'var(--muted-foreground)' },
  { tag: t.monospace, color: 'var(--primary)' },
])
