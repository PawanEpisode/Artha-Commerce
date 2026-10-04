// Verifies WCAG contrast for every theme defined in src/styles.css. Run: pnpm --filter @artha/design-system check:contrast
// Parses OKLCH tokens, converts to sRGB, checks the pairs components actually use. Exit code 1 on any failure.
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
  const out = {}
  for (const m of block(selector).matchAll(/--([a-z-]+):\s*oklch\(([^)]+)\)/g)) {
    const [main, alpha] = m[2].split('/').map((s) => s.trim())
    const [l, c, h] = main.split(/\s+/).map(Number)
    out[m[1]] = { l, c, h, alpha: alpha === undefined ? 1 : Number(alpha) }
  }
  return out
}

function toLinear({ l, c, h }) {
  const a = c * Math.cos((h * Math.PI) / 180)
  const b = c * Math.sin((h * Math.PI) / 180)
  const l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3
  const m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3
  const s_ = (l - 0.0894841775 * a - 1.291485548 * b) ** 3
  const clamp = (x) => Math.min(1, Math.max(0, x))
  return [
    clamp(4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_),
    clamp(-1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_),
    clamp(-0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_),
  ]
}

const luminance = (rgb) => 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
const mix = (fg, bg, alpha) => fg.map((v, i) => v * alpha + bg[i] * (1 - alpha))
const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}
const toHex = (rgb) =>
  '#' +
  rgb
    .map((v) => Math.round((v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055) * 255))
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
]
const ADVISORY = []

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
}

if (failures > 0) {
  console.error(`\n${failures} contrast check(s) failed`)
  process.exit(1)
}
console.log('\nAll required contrast checks passed')
