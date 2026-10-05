import { type OgCard, titleSize } from './og-card'

// The card is a raster image, so it cannot read CSS tokens. These mirror the brand colours of public/og/default.png.
const COLOURS = {
  from: '#1b1747',
  to: '#4a3fd6',
  text: '#ffffff',
  accent: '#7ef0c6',
  muted: '#d9d6ff',
  pill: 'rgba(255,255,255,0.14)',
}

export const OG_SIZE = { width: 1200, height: 630 } as const

type Node = { type: string; props: Record<string, unknown> }
const h = (
  type: string,
  style: Record<string, unknown>,
  children?: unknown,
  extra: Record<string, unknown> = {},
): Node => ({
  type,
  props: { style: { display: 'flex', ...style }, children, ...extra },
})

function decode(dataUrl: string): ArrayBuffer {
  const bytes = Buffer.from(dataUrl.slice(dataUrl.indexOf(',') + 1), 'base64')
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer
}

let fonts: Promise<Array<{ name: string; data: ArrayBuffer; weight: 400 | 700 | 800; style: 'normal' }>> | undefined
function loadFonts() {
  fonts ??= Promise.all([
    import('@fontsource/inter/files/inter-latin-400-normal.woff?inline'),
    import('@fontsource/inter/files/inter-latin-700-normal.woff?inline'),
    import('@fontsource/inter/files/inter-latin-800-normal.woff?inline'),
  ]).then(([r, b, x]) => [
    { name: 'Inter', data: decode(r.default), weight: 400 as const, style: 'normal' as const },
    { name: 'Inter', data: decode(b.default), weight: 700 as const, style: 'normal' as const },
    { name: 'Inter', data: decode(x.default), weight: 800 as const, style: 'normal' as const },
  ])
  return fonts
}

function layout(card: OgCard, brand: string): Node {
  return h(
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
      h('div', { fontSize: 34, fontWeight: 700, color: COLOURS.muted }, brand),
      h('div', { flexDirection: 'column' }, [
        h(
          'div',
          { fontSize: 32, fontWeight: 700, color: COLOURS.accent, letterSpacing: 2, textTransform: 'uppercase' },
          card.eyebrow,
        ),
        h('div', { fontSize: titleSize(card.title), fontWeight: 800, lineHeight: 1.08, marginTop: 18 }, card.title),
        h('div', { fontSize: 34, fontWeight: 400, color: COLOURS.muted, marginTop: 22 }, card.subtitle),
      ]),
      h(
        'div',
        { gap: 14 },
        card.facts.map((f) =>
          h(
            'div',
            { fontSize: 28, fontWeight: 700, padding: '10px 24px', borderRadius: 999, backgroundColor: COLOURS.pill },
            f,
          ),
        ),
      ),
    ],
  )
}

/** Renders a card to a 1200x630 PNG. Server only: loads satori, resvg and the bundled font on first use. */
export async function renderOgPng(card: OgCard, brand: string): Promise<Uint8Array> {
  const [{ default: satori }, { Resvg }, fontData] = await Promise.all([
    import('satori'),
    import('@resvg/resvg-js'),
    loadFonts(),
  ])
  const svg = await satori(layout(card, brand) as never, { ...OG_SIZE, fonts: fontData })
  return new Resvg(svg, { fitTo: { mode: 'width', value: OG_SIZE.width } }).render().asPng()
}
