// Generates the static 1200x630 social preview images and the app icons (512, 192 and maskable 512).
// Run: pnpm --filter @artha/web og   (output is committed; re-run when branding or the headline copy changes)
//
// Colours come from the design system: --primary and --accent of the Reading theme in
// packages/design-system/src/styles.css are read and converted from OKLCH to sRGB, so the card follows the brand.
// Text is drawn with the bundled Inter font via satori + resvg, so the output does not depend on fonts installed on
// the machine that runs the script.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

import { Resvg } from '@resvg/resvg-js'
import satori from 'satori'
import sharp from 'sharp'

const require = createRequire(import.meta.url)
const root = fileURLToPath(new URL('..', import.meta.url))
const stylesPath = fileURLToPath(new URL('../../../packages/design-system/src/styles.css', import.meta.url))

function oklchToHex(l, c, hDeg) {
  const h = (hDeg * Math.PI) / 180
  const a = c * Math.cos(h)
  const b = c * Math.sin(h)
  const l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3
  const m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3
  const s_ = (l - 0.0894841775 * a - 1.291485548 * b) ** 3
  const lin = [
    4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
    -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
    -0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_,
  ]
  const enc = (x) => {
    const v = Math.min(1, Math.max(0, x))
    return Math.round((v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055) * 255)
  }
  return `#${lin.map((x) => enc(x).toString(16).padStart(2, '0')).join('')}`
}

const css = readFileSync(stylesPath, 'utf8')
function token(name) {
  const m = css.match(new RegExp(`--${name}:\\s*oklch\\(([\\d.]+)\\s+([\\d.]+)\\s+([\\d.]+)\\)`))
  if (!m) throw new Error(`Token --${name} not found in design system styles.css`)
  return { l: Number(m[1]), c: Number(m[2]), h: Number(m[3]) }
}
const primary = token('primary')
const accent = token('accent')
const COLOURS = {
  from: oklchToHex(0.2, primary.c * 0.6, primary.h),
  to: oklchToHex(primary.l + 0.04, primary.c, primary.h),
  accent: oklchToHex(0.88, accent.c, accent.h),
  text: '#ffffff',
  muted: oklchToHex(0.86, 0.04, primary.h),
  pill: 'rgba(255,255,255,0.14)',
}
const MARK_AMBER = oklchToHex(0.83, 0.15, 78) // same amber as LogoMark in the design system

const font = (file) => readFileSync(require.resolve(`@fontsource/inter/files/${file}`))
const fonts = [
  { name: 'Inter', data: font('inter-latin-400-normal.woff'), weight: 400, style: 'normal' },
  { name: 'Inter', data: font('inter-latin-700-normal.woff'), weight: 700, style: 'normal' },
  { name: 'Inter', data: font('inter-latin-800-normal.woff'), weight: 800, style: 'normal' },
]

const el = (type, style, children, props = {}) => ({
  type,
  props: { style: { display: 'flex', ...style }, children, ...props },
})

const logoMark = el('div', { width: 76, height: 76 }, [
  {
    type: 'svg',
    props: {
      width: 76,
      height: 76,
      viewBox: '0 0 32 32',
      children: [
        { type: 'rect', props: { width: 32, height: 32, rx: 9, fill: '#ffffff' } },
        {
          type: 'path',
          props: {
            d: 'M9 22 16 8l7 14',
            fill: 'none',
            stroke: oklchToHex(primary.l, primary.c, primary.h),
            strokeWidth: 2.6,
            strokeLinecap: 'round',
            strokeLinejoin: 'round',
          },
        },
        { type: 'path', props: { d: 'M12 18h8', stroke: MARK_AMBER, strokeWidth: 2.6, strokeLinecap: 'round' } },
      ],
    },
  },
])

const cards = {
  default: {
    line1: 'Your entire exam prep,',
    line2: 'in one calm workspace.',
    sub: 'Study planner · Syllabus tracker · Focus timer',
    foot: 'For CA, CS and CMA students in India',
  },
  features: {
    line1: 'Tools that keep',
    line2: 'your prep on track.',
    sub: 'Syllabus tracker · Pomodoro timer · Study hours',
    foot: 'Built for CA, CS and CMA students',
  },
  courses: {
    line1: 'CA, CS and CMA,',
    line2: 'paper by paper.',
    sub: 'Every level, subject and chapter with marks weightage',
    foot: 'Plan, track and revise with ArthaCommerce',
  },
}

function layout(c) {
  return el(
    'div',
    {
      width: '100%',
      height: '100%',
      flexDirection: 'column',
      justifyContent: 'space-between',
      padding: '72px 80px',
      color: COLOURS.text,
      fontFamily: 'Inter',
      backgroundImage: `linear-gradient(135deg, ${COLOURS.from}, ${COLOURS.to})`,
    },
    [
      el('div', { alignItems: 'center', gap: 22, fontSize: 40, fontWeight: 700 }, [logoMark, 'ArthaCommerce']),
      el('div', { flexDirection: 'column' }, [
        el('div', { fontSize: 78, fontWeight: 800, lineHeight: 1.1 }, c.line1),
        el('div', { fontSize: 78, fontWeight: 800, lineHeight: 1.1, color: COLOURS.accent }, c.line2),
        el('div', { fontSize: 32, fontWeight: 400, color: COLOURS.muted, marginTop: 28 }, c.sub),
      ]),
      el('div', { fontSize: 28, fontWeight: 700, color: COLOURS.muted }, c.foot),
    ],
  )
}

mkdirSync(`${root}/public/og`, { recursive: true })
for (const [name, card] of Object.entries(cards)) {
  const svg = await satori(layout(card), { width: 1200, height: 630, fonts })
  const png = new Resvg(svg, { fitTo: { mode: 'width', value: 1200 } }).render().asPng()
  const out = await sharp(png).png({ compressionLevel: 9, palette: true, quality: 90, effort: 10 }).toBuffer()
  if (out.length > 300 * 1024) throw new Error(`${name}.png is ${out.length} bytes, WhatsApp needs < 300 KB`)
  writeFileSync(`${root}/public/og/${name}.png`, out)
  console.log(`public/og/${name}.png ${(out.length / 1024).toFixed(0)} KB`)
}

// App icons. The rounded one is the "any" icon (and the apple-touch icon). The maskable one is full-bleed with the same
// mark: Android crops it to a circle or squircle, and the mark sits well inside the centre 80% safe zone.
const primaryHex = oklchToHex(primary.l, primary.c, primary.h)
const iconSvg = ({ maskable }) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 32 32"><rect width="32" height="32"${maskable ? '' : ' rx="9"'} fill="${primaryHex}"/><path d="M9 22 16 8l7 14" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 18h8" stroke="${MARK_AMBER}" stroke-width="2.6" stroke-linecap="round"/></svg>`
await sharp(Buffer.from(iconSvg({ maskable: false })))
  .png()
  .toFile(`${root}/public/icon-512.png`)
await sharp(Buffer.from(iconSvg({ maskable: false })))
  .resize(192, 192)
  .png()
  .toFile(`${root}/public/icon-192.png`)
await sharp(Buffer.from(iconSvg({ maskable: true })))
  .png()
  .toFile(`${root}/public/icon-maskable-512.png`)
console.log('public/icon-512.png, icon-192.png, icon-maskable-512.png')
