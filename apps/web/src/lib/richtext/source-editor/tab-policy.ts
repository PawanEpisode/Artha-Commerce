/**
 * Tab inside a list indents the item, like every notes app. That would trap keyboard users (WCAG 2.1.2), so Escape
 * hands Tab back: after Escape the next Tab or Shift+Tab moves focus out of the box, then the editor goes back to
 * indenting. Pure so it can be tested without a browser.
 */
const LIST_LINE = /^\s*(?:[-*+]|\d+[.)])\s/

export const isListLine = (line: string) => LIST_LINE.test(line)

export function createTabPolicy() {
  let released = false
  return {
    /** Escape pressed: the next Tab leaves the editor. */
    release() {
      released = true
    },
    /** Any other key, or losing focus, puts the editor back to indenting. */
    reset() {
      released = false
    },
    /** True when this Tab should indent (and be swallowed); false when it must move focus. */
    shouldIndent(line: string, outdent: boolean): boolean {
      if (released) {
        released = false
        return false
      }
      return outdent ? /^\s/.test(line) : isListLine(line)
    },
  }
}
