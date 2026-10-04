/**
 * Writes supabase/templates/*.html and the template section of supabase/config.toml's companion file.
 *   pnpm --filter @artha/email-templates build     regenerate
 *   pnpm --filter @artha/email-templates check     fail if committed files differ (used in CI)
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { templates } from '../src/templates'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const outDir = resolve(root, 'supabase/templates')
const check = process.argv.includes('--check')

mkdirSync(outDir, { recursive: true })
let stale = 0
for (const t of templates) {
  const path = resolve(outDir, t.file)
  if (check) {
    let current = ''
    try {
      current = readFileSync(path, 'utf8')
    } catch {
      /* missing counts as stale */
    }
    if (current !== t.html) {
      stale++
      console.error(`stale: supabase/templates/${t.file}`)
    }
  } else {
    writeFileSync(path, t.html)
    console.log(`wrote supabase/templates/${t.file}`)
  }
}
if (check) {
  if (stale > 0) {
    console.error(`${stale} template(s) out of date. Run: pnpm emails:build`)
    process.exit(1)
  }
  console.log('Email templates are up to date')
}
