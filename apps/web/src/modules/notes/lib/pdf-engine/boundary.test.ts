import { fileURLToPath } from 'node:url'

import { ESLint } from 'eslint'
import { describe, expect, it } from 'vitest'

/**
 * The ESLint boundary of ERD decision 1: `pdfjs-dist` is imported only inside `lib/pdf-engine`. This lints the same
 * import from two places with the repo's real config: refused outside the folder, allowed inside it.
 */
const root = fileURLToPath(new URL('../../../../../../../', import.meta.url))
const code = "import { getDocument } from 'pdfjs-dist'\n\nexport const open = getDocument\n"

async function lint(filePath: string) {
  const eslint = new ESLint({ cwd: root })
  const [result] = await eslint.lintText(code, { filePath: `${root}${filePath}` })
  return (result?.messages ?? []).filter((m) => m.ruleId === 'no-restricted-imports')
}

describe('pdfjs-dist import boundary', () => {
  it('refuses the import in a component, a hook, a container and another module', async () => {
    for (const path of [
      'apps/web/src/modules/notes/components/Anything.ts',
      'apps/web/src/modules/notes/hooks/useAnything.ts',
      'apps/web/src/modules/notes/lib/other.ts',
      'apps/web/src/modules/tracker/lib/x.ts',
      'apps/web/src/routes/x.ts',
    ]) {
      const messages = await lint(path)
      expect(messages.map((m) => m.message).join(' '), path).toMatch(/pdf-engine/)
    }
  }, 60_000)

  it('allows it in the engine folder', async () => {
    expect(await lint('apps/web/src/modules/notes/lib/pdf-engine/pdfjs.ts')).toEqual([])
  }, 60_000)
})
