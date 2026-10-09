/**
 * Card text is Markdown-lite: paragraphs, `**bold**`, `*italic*` and `` `code` ``. It is shown as React text, never as HTML,
 * so nothing a card holds can run. This tokenizer is pure so the rules can be tested.
 */

export type Inline = { kind: 'text' | 'bold' | 'italic' | 'code'; text: string }
export type Line = Inline[]
export type Paragraph = Line[]

const PATTERN = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\*(?!\s)[^*\n]+?(?<!\s)\*|(?<!\w)_(?!\s)[^_\n]+?(?<!\s)_(?!\w))/g

export function tokenizeLine(line: string): Line {
  const out: Inline[] = []
  for (const part of line.split(PATTERN)) {
    if (part === '') continue
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4)
      out.push({ kind: 'bold', text: part.slice(2, -2) })
    else if (part.startsWith('`') && part.endsWith('`') && part.length > 2)
      out.push({ kind: 'code', text: part.slice(1, -1) })
    else if ((part.startsWith('*') && part.endsWith('*')) || (part.startsWith('_') && part.endsWith('_'))) {
      out.push(part.length > 2 ? { kind: 'italic', text: part.slice(1, -1) } : { kind: 'text', text: part })
    } else out.push({ kind: 'text', text: part })
  }
  return out
}

/** Paragraphs are separated by a blank line; a single line break stays a line break. */
export function tokenize(text: string): Paragraph[] {
  return text
    .replaceAll('\r\n', '\n')
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0)
    .map((p) => p.split('\n').map(tokenizeLine))
}

/** The text of a Markdown-lite string with its marks removed, on one line. For lists and labels. */
export function plain(markdown: string): string {
  return tokenize(markdown)
    .map((p) => p.map((l) => l.map((i) => i.text).join('')).join(' '))
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim()
}
