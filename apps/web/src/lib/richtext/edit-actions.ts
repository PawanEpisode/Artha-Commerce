/**
 * Pure text edits behind the editor toolbar. Each takes the text and the selection and returns the new text and
 * selection, so the textarea (a controlled input) only has to apply the result.
 */

export interface Edit {
  value: string
  start: number
  end: number
}

const lineStart = (value: string, index: number) => value.lastIndexOf('\n', index - 1) + 1
const lineEnd = (value: string, index: number) => {
  const found = value.indexOf('\n', index)
  return found === -1 ? value.length : found
}

/** Wraps the selection in a marker (`**`, `*`, `` ` ``), or removes the marker when it is already there. */
export function toggleInline({ value, start, end }: Edit, marker: string, placeholder: string): Edit {
  const before = value.slice(0, start)
  const selected = value.slice(start, end)
  const after = value.slice(end)
  if (before.endsWith(marker) && after.startsWith(marker)) {
    return {
      value: before.slice(0, -marker.length) + selected + after.slice(marker.length),
      start: start - marker.length,
      end: end - marker.length,
    }
  }
  const text = selected || placeholder
  const next = before + marker + text + marker + after
  return { value: next, start: start + marker.length, end: start + marker.length + text.length }
}

/**
 * Applies a prefix to every selected line, or removes it when every one already has it (`has`). Whatever marker a line
 * had before (`strip`) is replaced, so a bullet becomes a task instead of "- [ ] - text".
 */
function prefixLines(edit: Edit, prefix: (index: number) => string, has: RegExp, strip: RegExp = has): Edit {
  const from = lineStart(edit.value, edit.start)
  const to = lineEnd(edit.value, edit.end)
  const lines = edit.value.slice(from, to).split('\n')
  const allHave = lines.every((line) => has.test(line))
  const next = lines.map((line, i) => (allHave ? line.replace(has, '') : prefix(i) + line.replace(strip, '')))
  const block = next.join('\n')
  return { value: edit.value.slice(0, from) + block + edit.value.slice(to), start: from, end: from + block.length }
}

const ANY_MARKER = /^\s*(\d+\.|[-*+])\s(\[[ xX]\]\s)?/

export const bulletList = (e: Edit) => prefixLines(e, () => '- ', /^\s*[-*+]\s(?!\[[ xX]\])/, ANY_MARKER)
export const numberedList = (e: Edit) => prefixLines(e, (i) => `${i + 1}. `, /^\s*\d+\.\s/, ANY_MARKER)
export const taskList = (e: Edit) => prefixLines(e, () => '- [ ] ', /^\s*[-*+]\s\[[ xX]\]\s/, ANY_MARKER)
export const quote = (e: Edit) => prefixLines(e, () => '> ', /^\s*>\s?/)

/** Heading on the current line: none -> level `min`, then up to `max`, then back to none. */
export function cycleHeading(edit: Edit, min = 2, max = 4): Edit {
  const from = lineStart(edit.value, edit.start)
  const to = lineEnd(edit.value, edit.start)
  const line = edit.value.slice(from, to)
  const match = /^(#{1,6})\s+/.exec(line)
  const level = match?.[1]?.length ?? 0
  const body = line.replace(/^#{1,6}\s+/, '')
  const nextLevel = level === 0 ? min : level >= max ? 0 : level + 1
  const next = nextLevel === 0 ? body : `${'#'.repeat(nextLevel)} ${body}`
  return { value: edit.value.slice(0, from) + next + edit.value.slice(to), start: from, end: from + next.length }
}

/** Puts a block on its own lines: a blank line before and after unless the text already starts or ends one. */
function insertBlock(edit: Edit, block: string, select: [number, number]): Edit {
  const before = edit.value.slice(0, edit.start)
  const after = edit.value.slice(edit.end)
  const lead = before === '' || before.endsWith('\n\n') ? '' : before.endsWith('\n') ? '\n' : '\n\n'
  const trail = after === '' ? '\n' : after.startsWith('\n\n') ? '' : after.startsWith('\n') ? '\n' : '\n\n'
  const offset = before.length + lead.length
  return { value: before + lead + block + trail + after, start: offset + select[0], end: offset + select[1] }
}

export function insertTable(edit: Edit, rows = 2, cols = 3): Edit {
  const header = `| ${Array.from({ length: cols }, (_, i) => `Column ${i + 1}`).join(' | ')} |`
  const delimiter = `| ${Array.from({ length: cols }, () => '---').join(' | ')} |`
  const body = Array.from({ length: rows }, () => `| ${Array.from({ length: cols }, () => ' ').join(' | ')} |`)
  const block = [header, delimiter, ...body].join('\n')
  return insertBlock(edit, block, [2, 2 + 'Column 1'.length])
}

/** Inline formula `$x$`; with `display` a `$$` block on its own lines. The placeholder is selected for typing over. */
export function insertFormula(edit: Edit, display = false): Edit {
  if (display) {
    const block = '$$\n\\frac{a}{b}\n$$'
    return insertBlock(edit, block, [3, 3 + '\\frac{a}{b}'.length])
  }
  const selected = edit.value.slice(edit.start, edit.end)
  const text = selected || 'x^2'
  const next = `${edit.value.slice(0, edit.start)}$${text}$${edit.value.slice(edit.end)}`
  return { value: next, start: edit.start + 1, end: edit.start + 1 + text.length }
}

/** `![alt](attachment:<id>)` at the selection. An empty alt means "decorative", a choice the student made. */
export function insertImage(edit: Edit, attachmentId: string, alt: string): Edit {
  const markdown = `![${alt.replace(/[[\]]/g, '')}](attachment:${attachmentId})`
  const next = edit.value.slice(0, edit.start) + markdown + edit.value.slice(edit.end)
  const cursor = edit.start + markdown.length
  return { value: next, start: cursor, end: cursor }
}
