/**
 * Browser-side photo preparation for the avatar (PRD 5.5): validate the file, find the crop, draw a 512 px square.
 * The pure checks are unit tested; the canvas work only runs in a browser.
 */

export const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'] as const
export const MAX_FILE_BYTES = 10 * 1024 * 1024
export const MIN_SIDE_PX = 128
export const OUTPUT_PX = 512
/** The server refuses more than 1 MB, so the canvas result is brought under 900 KB. */
export const MAX_OUTPUT_BYTES = 900 * 1024

export type ImageFileProblem = 'type' | 'size' | 'small' | 'unreadable'

export function checkImageFile(file: { type: string; size: number }): ImageFileProblem | null {
  if (!(ACCEPTED_TYPES as ReadonlyArray<string>).includes(file.type)) return 'type'
  if (file.size > MAX_FILE_BYTES) return 'size'
  return null
}

export const checkImageSize = (width: number, height: number): ImageFileProblem | null =>
  Math.min(width, height) < MIN_SIDE_PX ? 'small' : null

/** Student-facing sentence for each problem (PRD 5.5 states table). */
export const IMAGE_PROBLEM_TEXT: Record<ImageFileProblem, string> = {
  type: 'Use a JPG, PNG or WebP image.',
  size: 'That photo is over 10 MB. Choose a smaller one.',
  small: 'Choose a photo at least 128 by 128 pixels.',
  unreadable: 'We could not read that photo. Try another one.',
}

export interface PixelCrop {
  x: number
  y: number
  width: number
  height: number
}

/** Decode a file in the browser (EXIF orientation is applied by the browser). Resolves with the object URL and size. */
export function loadImage(file: File): Promise<{ url: string; width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => resolve({ url, width: img.naturalWidth, height: img.naturalHeight })
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('unreadable'))
    }
    img.src = url
  })
}

const toBlob = (canvas: HTMLCanvasElement, type: string, quality: number) =>
  new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, type, quality))

/** Draw the chosen square to 512 px and encode it (WebP, else JPEG), lowering quality until it is small enough. */
export async function cropToBlob(url: string, crop: PixelCrop): Promise<Blob> {
  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const el = new Image()
    el.onload = () => resolve(el)
    el.onerror = () => reject(new Error('unreadable'))
    el.src = url
  })
  const canvas = document.createElement('canvas')
  canvas.width = OUTPUT_PX
  canvas.height = OUTPUT_PX
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('unreadable')
  ctx.imageSmoothingQuality = 'high'
  ctx.drawImage(img, crop.x, crop.y, crop.width, crop.height, 0, 0, OUTPUT_PX, OUTPUT_PX)
  for (const type of ['image/webp', 'image/jpeg']) {
    for (const quality of [0.9, 0.8, 0.7, 0.55]) {
      const blob = await toBlob(canvas, type, quality)
      if (blob && blob.type === type && blob.size <= MAX_OUTPUT_BYTES) return blob
    }
  }
  throw new Error('unreadable')
}

/** Rough size bucket for analytics: never the exact size. */
export const bytesBucket = (bytes: number) =>
  bytes < 100_000 ? 'lt_100kb' : bytes < 300_000 ? '100_300kb' : bytes < 600_000 ? '300_600kb' : 'gt_600kb'
