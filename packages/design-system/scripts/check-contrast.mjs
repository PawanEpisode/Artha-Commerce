// Verifies WCAG contrast for every theme defined in src/styles.css. Run: pnpm --filter @artha/design-system check:contrast
// Parses OKLCH tokens, converts to sRGB, checks the pairs components actually use. Exit code 1 on any failure.
//
// ANNOTATION MARKS (F-03, PRD FR-F03-15): highlight, ink and page tokens are checked against each page tone (original =
// --page-original, paper = --page-paper, night = --page-night) in every theme, using the blend the reader really uses:
// multiply on original and paper, screen on night, computed on gamma-encoded sRGB like a browser does.
// DECISION, physical limit: a highlight FILL cannot reach 3:1 against a white or paper page and still be a highlight. With
// multiply the page shows through, so the fill is the page times the colour; 3:1 would need a relative luminance below
// about 0.30 (a mid-tone, close to the pen colours), which dims the very words it marks and removes the difference
// between a highlighter and a marker. So the fill is held to a 1.5:1 sanity floor (it must not vanish) and the 3:1 rule
// (WCAG 1.4.11) is enforced on --highlight-*-edge, the stroke the annotation layer draws under and around every
// highlight and uses for underlines, plus on --ink-* (pens). Colour is never the only signal: SwatchPicker adds a name
// and a shape. On a night page the fill is screened and easily clears 3:1 as well.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const css = readFileSync(fileURLToPath(new URL('../src/styles.css', import.meta.url)), 'utf8')

/** Theme name -> selector fragment that starts its token block. */
const THEMES = {
  reading: ":root,\n:root[data-theme='reading']",
  light: ":root[data-theme='light']",
  dark: ":root[data-theme='dark'],\n.dark",
}

function block(selector) {
  const start = css.indexOf(`${selector} {`)
  if (start === -1) throw new Error(`Theme block not found: ${selector}`)
  return css.slice(start, css.indexOf('\n}', start))
}

function tokens(selector) {
  // Page tones belong to the document, not to a theme: they are declared once on :root and inherited by every theme.
  const out =
    selector === THEMES.reading
      ? {}
      : Object.fromEntries(Object.entries(tokens(THEMES.reading)).filter(([k]) => k.startsWith('page-')))
  for (const m of block(selector).matchAll(/--([a-z0-9-]+):\s*oklch\(([^)]+)\)/g)) {
    const [main, alpha] = m[2].split('/').map((s) => s.trim())
    const [l, c, h] = main.split(/\s+/).map(Number)
    out[m[1]] = { l, c, h, alpha: alpha === undefined ? 1 : Number(alpha) }
  }
  return out
}

function rawLinear({ l, c, h }) {
  const a = c * Math.cos((h * Math.PI) / 180)
  const b = c * Math.sin((h * Math.PI) / 180)
  const l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3
  const m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3
  const s_ = (l - 0.0894841775 * a - 1.291485548 * b) ** 3
  return [
    4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
    -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
    -0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_,
  ]
}
const clamp01 = (x) => Math.min(1, Math.max(0, x))
const toLinear = (tok) => rawLinear(tok).map(clamp01)
/** True when the colour is inside sRGB, so a browser and this script agree on it (no gamut mapping involved). */
const inGamut = (tok) => rawLinear(tok).every((v) => v >= -0.0005 && v <= 1.0005)
const encode = (v) => (v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055)
const decode = (v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
/** Browsers blend on gamma-encoded sRGB values, not on linear light. */
const blend = (mode, fg, page) =>
  fg.map((v, i) => {
    const s = encode(v)
    const b = encode(page[i])
    return decode(mode === 'multiply' ? s * b : mode === 'screen' ? 1 - (1 - s) * (1 - b) : s)
  })

const luminance = (rgb) => 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
const mix = (fg, bg, alpha) => fg.map((v, i) => v * alpha + bg[i] * (1 - alpha))
const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}
const toHex = (rgb) =>
  '#' +
  rgb
    .map((v) => Math.round(encode(v) * 255))
    .map((n) => n.toString(16).padStart(2, '0'))
    .join('')

// [foreground token, background token, minimum ratio, why]
const REQUIRED = [
  ['foreground', 'background', 7, 'body text (AAA)'],
  ['card-foreground', 'card', 7, 'text on cards (AAA)'],
  ['popover-foreground', 'popover', 4.5, 'menus'],
  ['primary-foreground', 'primary', 4.5, 'primary buttons'],
  ['secondary-foreground', 'secondary', 4.5, 'secondary buttons'],
  ['accent-foreground', 'accent', 4.5, 'accent buttons'],
  ['highlight-foreground', 'highlight', 4.5, 'highlight chips'],
  ['muted-foreground', 'background', 4.5, 'secondary text on page'],
  ['muted-foreground', 'card', 4.5, 'secondary text on cards'],
  ['muted-foreground', 'muted', 4.5, 'secondary text on muted areas'],
  ['primary', 'background', 4.5, 'links and text-primary on page'],
  ['primary', 'card', 4.5, 'links and text-primary on cards'],
  ['destructive', 'background', 4.5, 'error text on page'],
  ['destructive', 'card', 4.5, 'error text on cards'],
  ['ring', 'background', 3, 'focus indicator (WCAG 2.2 non-text)'],
  ['ring', 'card', 3, 'focus indicator on cards'],
  ['input', 'card', 3, 'form field border (WCAG 1.4.11)'],
  ['input', 'background', 3, 'form field border on page (WCAG 1.4.11)'],
  ['primary-foreground', 'destructive', 3, 'confidence marker icon'],
  ['primary', 'secondary', 3, 'progress fill on track (WCAG 1.4.11)'],
  ['primary', 'card', 3, 'progress ring on card'],
  ['destructive', 'secondary', 3, 'progress fill (destructive) on track'],
  ['chart-1', 'card', 3, 'chart series 1 on card (WCAG 1.4.11)'],
  ['chart-2', 'card', 3, 'chart series 2 on card (WCAG 1.4.11)'],
  ['chart-3', 'card', 3, 'chart series 3 on card (WCAG 1.4.11)'],
  ['chart-4', 'card', 3, 'chart series 4 on card (WCAG 1.4.11)'],
  ['chart-5', 'card', 3, 'chart series 5 on card (WCAG 1.4.11)'],
  ['error-fg', 'error-bg', 4.5, 'error text on its tint'],
  ['error', 'card', 3, 'error icon on card (WCAG 1.4.11)'],
  ['error-fg', 'background', 4.5, 'error text on the page (dropzone error line)'],
  ['error-border', 'background', 1.5, 'error border is decorative'],
  ['success-fg', 'success-bg', 4.5, 'success text on its tint'],
  ['primary', 'success-bg', 3, 'floating timer: progress ring on the phase-end tint (WCAG 1.4.11)'],
  ['foreground', 'success-bg', 4.5, 'floating timer: icon buttons on the phase-end tint'],
  ['ring', 'success-bg', 3, 'floating timer: focus indicator on the phase-end tint'],
  ['success', 'card', 3, 'success icon, dot and rail on card (WCAG 1.4.11)'],
  ['success', 'background', 3, 'success accent on page'],
  ['success-border', 'background', 1.5, 'success border is decorative'],
  ['warning-fg', 'warning-bg', 4.5, 'warning text on its tint'],
  ['warning', 'card', 3, 'warning icon, dot and rail on card (WCAG 1.4.11)'],
  ['warning', 'background', 3, 'warning accent on page'],
  ['warning-border', 'background', 1.5, 'warning border is decorative'],
  ['info-fg', 'info-bg', 4.5, 'info text on its tint'],
  ['info', 'card', 3, 'info icon, dot and rail on card (WCAG 1.4.11)'],
  ['info', 'background', 3, 'info accent on page'],
  ['info-border', 'background', 1.5, 'info border is decorative'],
  ['tag-chapter-fg', 'tag-chapter-bg', 4.5, 'tag-chapter text on its tint'],
  ['tag-chapter', 'card', 3, 'tag-chapter icon, dot and rail on card (WCAG 1.4.11)'],
  ['tag-chapter', 'background', 3, 'tag-chapter accent on page'],
  ['tag-chapter-border', 'background', 1.5, 'tag-chapter border is decorative'],
  ['tag-topic-fg', 'tag-topic-bg', 4.5, 'tag-topic text on its tint'],
  ['tag-topic', 'card', 3, 'tag-topic icon, dot and rail on card (WCAG 1.4.11)'],
  ['tag-topic', 'background', 3, 'tag-topic accent on page'],
  ['tag-topic-border', 'background', 1.5, 'tag-topic border is decorative'],
  ['tag-paper-fg', 'tag-paper-bg', 4.5, 'tag-paper text on its tint'],
  ['tag-paper', 'card', 3, 'tag-paper icon, dot and rail on card (WCAG 1.4.11)'],
  ['tag-paper', 'background', 3, 'tag-paper accent on page'],
  ['tag-paper-border', 'background', 1.5, 'tag-paper border is decorative'],
  ['avatar-1-fg', 'avatar-1', 4.5, 'initials on avatar colour 1'],
  ['avatar-2-fg', 'avatar-2', 4.5, 'initials on avatar colour 2'],
  ['avatar-3-fg', 'avatar-3', 4.5, 'initials on avatar colour 3'],
  ['avatar-4-fg', 'avatar-4', 4.5, 'initials on avatar colour 4'],
  ['avatar-5-fg', 'avatar-5', 4.5, 'initials on avatar colour 5'],
  ['avatar-6-fg', 'avatar-6', 4.5, 'initials on avatar colour 6'],
  ['avatar-7-fg', 'avatar-7', 4.5, 'initials on avatar colour 7'],
  ['avatar-8-fg', 'avatar-8', 4.5, 'initials on avatar colour 8'],
]
const ADVISORY = []

// Annotation marks. Blend: multiply (original, paper) and screen (night) for highlights, normal for pens.
const TONES = {
  original: ['page-original', 'multiply'],
  paper: ['page-paper', 'multiply'],
  night: ['page-night', 'screen'],
}
const KEYS = ['yellow', 'green', 'blue', 'pink', 'orange']
const PENS = [1, 2, 3, 4, 5]
// [token, minimum ratio on the page, blend kind, why]
const MARK_TOKENS = [
  ...KEYS.map((k) => [
    `highlight-${k}`,
    1.5,
    'highlight',
    'fill: sanity floor, 3:1 is physically out of reach (see top of file)',
  ]),
  ...KEYS.map((k) => [`highlight-${k}-edge`, 3, 'highlight', 'edge and underline stroke (WCAG 1.4.11, FR-F03-15)']),
  ...PENS.map((n) => [`ink-${n}`, 3, 'normal', 'pen stroke (WCAG 1.4.11)']),
]
// Strokes and pens as shown in a swatch on the app surface.
const SWATCH_ON_CARD = [...KEYS.map((k) => `highlight-${k}-edge`), ...PENS.map((n) => `ink-${n}`)]

let failures = 0
for (const [theme, selector] of Object.entries(THEMES)) {
  const t = tokens(selector)
  const rgbOf = (name, over) => {
    const tok = t[name]
    if (!tok) throw new Error(`${theme}: missing token --${name}`)
    const rgb = toLinear(tok)
    return tok.alpha < 1 && over ? mix(rgb, over, tok.alpha) : rgb
  }
  console.log(`\n${theme}  (background ${toHex(rgbOf('background'))}, card ${toHex(rgbOf('card'))})`)
  for (const [fg, bg, min, why] of REQUIRED) {
    const bgRgb = rgbOf(bg)
    const ratio = contrast(rgbOf(fg, bgRgb), bgRgb)
    const ok = ratio >= min
    if (!ok) failures++
    console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${fg} on ${bg}: ${ratio.toFixed(2)} (min ${min}) ${why}`)
  }
  for (const [fg, bg, min, why] of ADVISORY) {
    const bgRgb = rgbOf(bg)
    const ratio = contrast(rgbOf(fg, bgRgb), bgRgb)
    console.log(`  note ${fg} on ${bg}: ${ratio.toFixed(2)} (advisory ${min}) ${why}`)
  }

  const report = (ok, label, ratio, min, why) => {
    if (!ok) failures++
    console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${label}: ${ratio} (min ${min}) ${why}`)
  }
  for (const name of [...MARK_TOKENS.map(([n]) => n), 'swatch-marker', 'swatch-marker-inverse']) {
    if (!t[name]) throw new Error(`${theme}: missing token --${name}`)
    if (!inGamut(t[name]))
      report(false, `--${name}`, 'outside sRGB', 'in gamut', 'a browser would gamut-map it differently')
  }
  for (const [tone, [pageToken, mode]] of Object.entries(TONES)) {
    const page = rgbOf(pageToken)
    console.log(`  marks on the ${tone} page (${toHex(page)}; highlights ${mode})`)
    for (const [name, min, kind, why] of MARK_TOKENS) {
      const ratio = contrast(blend(kind === 'highlight' ? mode : 'normal', rgbOf(name), page), page)
      report(ratio >= min, `${name} on ${tone}`, ratio.toFixed(2), min, why)
    }
  }
  for (const name of SWATCH_ON_CARD) {
    const r = contrast(rgbOf(name), rgbOf('card'))
    report(r >= 3, `${name} on card`, r.toFixed(2), 3, 'swatch outline on the app surface (WCAG 1.4.11)')
  }
  for (const k of KEYS) {
    const r = contrast(rgbOf('swatch-marker'), rgbOf(`highlight-${k}`))
    report(r >= 4.5, `swatch-marker on highlight-${k}`, r.toFixed(2), 4.5, 'shape marker in a highlight swatch')
  }
  for (const n of PENS) {
    const r = contrast(rgbOf('swatch-marker-inverse'), rgbOf(`ink-${n}`))
    report(r >= 4.5, `swatch-marker-inverse on ink-${n}`, r.toFixed(2), 4.5, 'shape marker in a pen swatch')
  }
  console.log('  sRGB: ' + MARK_TOKENS.map(([n]) => `${n} ${toHex(rgbOf(n))}`).join(', '))
}

if (failures > 0) {
  console.error(`\n${failures} contrast check(s) failed`)
  process.exit(1)
}
console.log('\nAll required contrast checks passed')
