// Copies the pdf.js data files the reader needs at run time into public/pdfjs (gitignored, like public/sw.js).
// Runs before `vite dev` and `vite build`. The worker fetches them on demand, so they cost nothing until a PDF needs one:
//   cmaps/          predefined character maps (legacy Indian and CJK encodings that are not embedded)
//   standard_fonts/ the 14 standard fonts for PDFs that name Helvetica or Times without embedding them
//   wasm/           JBIG2, JPEG 2000 and colour-profile decoders (scanned and print-quality PDFs)
//   iccs/           the default CMYK profile
// Embedded fonts (most Devanagari PDFs) render without any of them.
import { cp, mkdir, rm } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'

const require = createRequire(import.meta.url)
const root = dirname(require.resolve('pdfjs-dist/package.json'))
const target = new URL('../public/pdfjs/', import.meta.url).pathname

await rm(target, { recursive: true, force: true })
await mkdir(target, { recursive: true })
for (const dir of ['cmaps', 'standard_fonts', 'wasm', 'iccs']) {
  await cp(join(root, dir), join(target, dir), { recursive: true })
}
