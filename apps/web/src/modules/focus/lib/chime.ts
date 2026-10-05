/**
 * The alert sound, synthesised with the Web Audio API (no audio files to ship or license). Two soft sine notes; the
 * volume setting scales the gain. Browsers only allow sound after a gesture, so `unlockAudio` runs on the Start click.
 */
let context: AudioContext | null = null

function ctx(): AudioContext | null {
  if (typeof window === 'undefined') return null
  const Ctor =
    window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!Ctor) return null
  context ??= new Ctor()
  return context
}

/** Call from a click handler so the browser lets later chimes play. Safe to call repeatedly. */
export function unlockAudio(): void {
  try {
    const c = ctx()
    if (c && c.state === 'suspended') void c.resume()
  } catch {
    // no audio available; the other alerts still work
  }
}

/** Gain for a 0 to 100 volume. Quadratic so the middle of the slider is not already loud. */
export function volumeToGain(volume: number): number {
  const v = Math.min(100, Math.max(0, volume)) / 100
  return v * v * 0.6
}

export function playChime(volume: number): boolean {
  try {
    const c = ctx()
    if (!c || volume <= 0) return false
    const gain = volumeToGain(volume)
    const now = c.currentTime
    for (const [i, freq] of [660, 880].entries()) {
      const osc = c.createOscillator()
      const g = c.createGain()
      osc.type = 'sine'
      osc.frequency.value = freq
      g.gain.setValueAtTime(0.0001, now + i * 0.22)
      g.gain.exponentialRampToValueAtTime(Math.max(0.0001, gain), now + i * 0.22 + 0.03)
      g.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.22 + 0.7)
      osc.connect(g).connect(c.destination)
      osc.start(now + i * 0.22)
      osc.stop(now + i * 0.22 + 0.75)
    }
    return true
  } catch {
    return false
  }
}
