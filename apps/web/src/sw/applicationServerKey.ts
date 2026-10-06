/** Thrown for a VAPID public key that is not URL-safe base64 of an uncompressed P-256 point (65 bytes). */
export class InvalidApplicationServerKey extends Error {
  constructor() {
    super('The VAPID public key is not a valid push key.')
  }
}

const P256_UNCOMPRESSED_BYTES = 65

/** Converts the URL-safe base64 VAPID public key (what `web-push generate-vapid-keys` prints) to bytes. */
export function urlBase64ToUint8Array(base64Url: string): Uint8Array<ArrayBuffer> {
  const value = base64Url.trim()
  if (!/^[A-Za-z0-9_-]+$/.test(value)) throw new InvalidApplicationServerKey()
  const base64 = value
    .replace(/-/g, '+')
    .replace(/_/g, '/')
    .padEnd(Math.ceil(value.length / 4) * 4, '=')
  const binary = atob(base64)
  const bytes = new Uint8Array(new ArrayBuffer(binary.length))
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
  if (bytes.length !== P256_UNCOMPRESSED_BYTES || bytes[0] !== 0x04) throw new InvalidApplicationServerKey()
  return bytes
}

/** True when the browser's key bytes equal ours, so an existing subscription can be reused. */
export function sameKey(a: ArrayBuffer | null | undefined, b: Uint8Array): boolean {
  if (!a || a.byteLength !== b.byteLength) return false
  const view = new Uint8Array(a)
  return view.every((byte, i) => byte === b[i])
}
