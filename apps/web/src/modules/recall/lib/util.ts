/** Index into an array that must have the element; a clear error instead of a silent `undefined`. */
export function at<T>(xs: readonly T[], i: number): T {
  const v = xs[i]
  if (v === undefined) throw new RangeError(`Index ${i} is out of range (length ${xs.length}).`)
  return v
}
