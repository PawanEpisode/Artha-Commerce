/**
 * F-12 Deep Link & Locator Mathematics
 * Converts official printed page numbers to direct PDF URL fragment locators.
 * Standard PDF viewers (Chrome, Safari, Firefox, Adobe, PDF.js) recognize `#page=N`.
 */

export interface LocatorOptions {
  pdfUrl?: string | null
  printedPage?: number | null
  pageOffset?: number
}

export function buildPdfDeepLink({ pdfUrl, printedPage, pageOffset = 0 }: LocatorOptions): string | null {
  if (!pdfUrl) return null
  if (printedPage === undefined || printedPage === null) return pdfUrl

  const pdfTargetPage = Math.max(1, printedPage + pageOffset)
  // Ensure we don't duplicate existing fragment
  const base = pdfUrl.split('#')[0]
  return `${base}#page=${pdfTargetPage}`
}

export function formatPageRange(startPage?: number | null, endPage?: number | null): string {
  if (startPage && endPage && startPage !== endPage) {
    return `pp. ${startPage}–${endPage}`
  }
  if (startPage) {
    return `p. ${startPage}`
  }
  return 'Page N/A'
}
