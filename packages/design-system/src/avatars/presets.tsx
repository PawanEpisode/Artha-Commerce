import type { ReactNode } from 'react'

import manifest from './manifest.json'

/** The 24 preset avatar keys (`p01` to `p24`). The API keeps the same list; a test compares them. */
export const AVATAR_PRESET_KEYS: ReadonlyArray<string> = manifest.keys

/** 12 motifs on a 64 by 64 canvas, drawn only with `currentColor`, which the Avatar sets to the colour's text token. */
const MOTIFS: ReadonlyArray<{ name: string; art: ReactNode }> = [
  { name: 'Ring', art: <circle cx="32" cy="32" r="14" fill="none" stroke="currentColor" strokeWidth="6" /> },
  {
    name: 'Sunrise',
    art: (
      <>
        <path d="M12 42a20 20 0 0 1 40 0z" fill="currentColor" />
        <rect x="8" y="46" width="48" height="5" rx="2.5" fill="currentColor" opacity=".6" />
      </>
    ),
  },
  {
    name: 'Peaks',
    art: (
      <>
        <path d="M6 50 24 20l12 18 8-10 14 22z" fill="currentColor" />
        <circle cx="46" cy="16" r="5" fill="currentColor" opacity=".6" />
      </>
    ),
  },
  {
    name: 'Book',
    art: (
      <>
        <path d="M32 22c-6-4-14-4-20-2v28c6-2 14-2 20 2z" fill="currentColor" />
        <path d="M32 22c6-4 14-4 20-2v28c-6-2-14-2-20 2z" fill="currentColor" opacity=".6" />
      </>
    ),
  },
  {
    name: 'Leaf',
    art: (
      <>
        <path d="M14 48C14 26 28 14 50 14c0 22-12 36-34 36z" fill="currentColor" />
        <path d="M14 50 36 28" stroke="currentColor" strokeWidth="3" opacity=".5" />
      </>
    ),
  },
  {
    name: 'Star',
    art: (
      <path d="M32 10l6.5 14 15.5 1.8-11.6 10.4L45.5 51 32 43l-13.5 8 3.1-14.8L10 25.8 25.5 24z" fill="currentColor" />
    ),
  },
  {
    name: 'Waves',
    art: (
      <g fill="none" stroke="currentColor" strokeWidth="5" strokeLinecap="round">
        <path d="M10 24q11-9 22 0t22 0" />
        <path d="M10 36q11-9 22 0t22 0" opacity=".7" />
        <path d="M10 48q11-9 22 0t22 0" opacity=".45" />
      </g>
    ),
  },
  {
    name: 'Diamonds',
    art: (
      <>
        <path d="M32 10 46 32 32 54 18 32z" fill="currentColor" />
        <path d="M32 22 38 32 32 42 26 32z" fill="currentColor" opacity=".35" />
      </>
    ),
  },
  {
    name: 'Stack',
    art: (
      <>
        <path d="M32 12 54 30H10z" fill="currentColor" />
        <path d="M32 26 56 46H8z" fill="currentColor" opacity=".6" />
      </>
    ),
  },
  {
    name: 'Flower',
    art: (
      <g fill="currentColor">
        <circle cx="32" cy="18" r="9" />
        <circle cx="46" cy="32" r="9" opacity=".8" />
        <circle cx="32" cy="46" r="9" />
        <circle cx="18" cy="32" r="9" opacity=".8" />
        <circle cx="32" cy="32" r="5" opacity=".35" />
      </g>
    ),
  },
  { name: 'Crescent', art: <path d="M40 12a22 22 0 1 0 12 28A18 18 0 0 1 40 12z" fill="currentColor" /> },
  { name: 'Bolt', art: <path d="M36 8 16 36h14l-4 20 22-30H34z" fill="currentColor" /> },
]

/** Colour index (1 to 8) of preset number `n` (1 to 24). A multiple of 3 spreads neighbours over the palette. */
const colourOf = (n: number) => (((n - 1) * 3) % 8) + 1

export interface PresetArt {
  key: string
  /** Spoken name, e.g. "Peaks". */
  name: string
  colour: number
  art: ReactNode
}

export function presetArt(key: string): PresetArt | null {
  const n = AVATAR_PRESET_KEYS.indexOf(key) + 1
  if (n === 0) return null
  const motif = MOTIFS[(n - 1) % MOTIFS.length] as (typeof MOTIFS)[number]
  return { key, name: motif.name, colour: colourOf(n), art: motif.art }
}
