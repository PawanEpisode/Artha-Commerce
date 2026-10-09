/**
 * Her recall data as files (FR-F15-75). The JSON is the whole export. The CSVs are streamed by the server and end with one
 * line that says whether the file is complete (`#complete,<rows>`); a download that lacks it was cut short and is refused,
 * never saved as if it were whole.
 */
import { ApiError, readAccessToken } from '~/lib/api'
import { env } from '~/lib/env'

export type CsvKind = 'cards' | 'reviews'

export const csvFileName = (kind: CsvKind, now: Date = new Date()): string => {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `recall-${kind}-${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}.csv`
}

export const jsonFileName = (now: Date = new Date()): string =>
  csvFileName('cards', now).replace('cards', 'data').replace('.csv', '.json')

/** The row count from the closing line, or null when the file does not end with `#complete,<n>`. */
export function completeRowCount(text: string): number | null {
  const last = text.trimEnd().split(/\r?\n/).pop() ?? ''
  const match = /^#complete,(\d+)$/.exec(last)
  return match ? Number(match[1]) : null
}

export async function fetchCsv(kind: CsvKind): Promise<{ text: string; rows: number }> {
  const token = await readAccessToken()
  const res = await fetch(`${env.VITE_API_URL}/api/v1/recall/export/${kind}.csv`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new ApiError(res.status, `API ${res.status} on export`, await res.json().catch(() => undefined))
  const text = await res.text()
  const rows = completeRowCount(text)
  if (rows === null) throw new ApiError(0, 'The download was cut short.')
  return { text, rows }
}

/** Saves a Blob through a temporary link, then frees it. Browser only. */
export function saveBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000)
}
