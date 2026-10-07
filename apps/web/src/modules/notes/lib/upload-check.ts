import type { DocumentQuotaDetails } from './errors'
import { formatBytes, pluralize } from './format'
import type { Usage } from './types'

/** Checks that run before any byte moves (FR-F03-01, PRD 5.5): type, file size, page count, storage and document count. */
export const MIB = 1024 * 1024

export interface UploadLimits {
  maxFileMb: number
  maxPages: number
  maxStorageMb: number
  maxDocuments: number
}

/** The free plan, for the moment before `GET usage/` answers. The server enforces the real numbers either way. */
export const FALLBACK_UPLOAD_LIMITS: UploadLimits = {
  maxFileMb: 50,
  maxPages: 1000,
  maxStorageMb: 500,
  maxDocuments: 100,
}

export function limitsFromUsage(usage: Usage | undefined): UploadLimits {
  if (!usage) return FALLBACK_UPLOAD_LIMITS
  const l = usage.limits
  return {
    maxFileMb: l.max_file_mb ?? FALLBACK_UPLOAD_LIMITS.maxFileMb,
    maxPages: l.max_pages ?? FALLBACK_UPLOAD_LIMITS.maxPages,
    maxStorageMb: l.max_storage_mb ?? FALLBACK_UPLOAD_LIMITS.maxStorageMb,
    maxDocuments: l.max_documents ?? FALLBACK_UPLOAD_LIMITS.maxDocuments,
  }
}

export interface FileFacts {
  name: string
  type: string
  bytes: number
  /** Null when the quick check could not read the page count (locked, damaged, or still reading). */
  pages: number | null
}

export type UploadRefusal =
  | { reason: 'type' }
  | { reason: 'too_large'; limitMb: number; bytes: number }
  | { reason: 'too_many_pages'; limit: number; pages: number }
  | { reason: 'quota'; kind: 'storage' | 'documents'; used: number; limit: number }

export const isPdfFile = (file: Pick<FileFacts, 'name' | 'type'>) =>
  file.type === 'application/pdf' || (file.type === '' && /\.pdf$/i.test(file.name))

/** The first reason this file must not be sent, or null. Type first, then size, pages, and last the account quota. */
export function checkBeforeUpload(
  file: FileFacts,
  limits: UploadLimits,
  used: { storageBytes: number; documents: number } | undefined,
): UploadRefusal | null {
  if (!isPdfFile(file)) return { reason: 'type' }
  if (file.bytes > limits.maxFileMb * MIB) return { reason: 'too_large', limitMb: limits.maxFileMb, bytes: file.bytes }
  if (file.pages !== null && file.pages > limits.maxPages)
    return { reason: 'too_many_pages', limit: limits.maxPages, pages: file.pages }
  if (used) {
    const storageLimit = limits.maxStorageMb * MIB
    if (used.storageBytes + file.bytes > storageLimit)
      return { reason: 'quota', kind: 'storage', used: used.storageBytes, limit: storageLimit }
    if (used.documents >= limits.maxDocuments)
      return { reason: 'quota', kind: 'documents', used: used.documents, limit: limits.maxDocuments }
  }
  return null
}

/** "50 MB limit (this file 63 MB)" and what to try, in plain words. */
export function refusalText(refusal: UploadRefusal): { title: string; hint: string } {
  switch (refusal.reason) {
    case 'type':
      return { title: 'This does not look like a PDF', hint: 'Choose a file that ends in .pdf. Nothing was uploaded.' }
    case 'too_large':
      return {
        title: `${refusal.limitMb} MB limit (this file ${formatBytes(refusal.bytes)})`,
        hint: 'Split the PDF into parts or compress it, then choose it again.',
      }
    case 'too_many_pages':
      return {
        title: `${pluralize(refusal.limit, 'page')} limit (this file has ${refusal.pages.toLocaleString('en-IN')})`,
        hint: 'Split the PDF into parts, for example one per chapter, then choose it again.',
      }
    case 'quota':
      return refusal.kind === 'storage'
        ? { title: 'Your PDF storage is full', hint: 'Free up space, then add this file.' }
        : { title: 'You have reached the number of PDFs your plan allows', hint: 'Delete one you no longer need.' }
  }
}

/** The quota details the quota sheet shows, from a pre-check refusal (kind, used, limit; the server adds the list). */
export function quotaFromRefusal(
  refusal: Extract<UploadRefusal, { reason: 'quota' }>,
  plan: string,
  largest: DocumentQuotaDetails['largest_documents'],
): DocumentQuotaDetails {
  return { kind: refusal.kind, used: refusal.used, limit: refusal.limit, plan, largest_documents: largest }
}

/** The quota that already blocks any upload (storage or the PDF count is at its limit), so Upload can open the quota sheet at once. */
export function fullQuota(usage: Usage | undefined): DocumentQuotaDetails | null {
  if (!usage) return null
  const limits = limitsFromUsage(usage)
  const storageLimit = limits.maxStorageMb * MIB
  const largest = usage.largest_documents
  if (usage.used.storage_bytes >= storageLimit)
    return {
      kind: 'storage',
      used: usage.used.storage_bytes,
      limit: storageLimit,
      plan: usage.plan,
      largest_documents: largest,
    }
  const documents = usage.used.documents ?? 0
  if (documents >= limits.maxDocuments)
    return {
      kind: 'documents',
      used: documents,
      limit: limits.maxDocuments,
      plan: usage.plan,
      largest_documents: largest,
    }
  return null
}
