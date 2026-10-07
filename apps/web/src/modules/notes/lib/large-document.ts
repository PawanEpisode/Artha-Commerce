/** Large-document mode (PRD 5.5): no thumbnails, two pages prefetched, server search, a one-line notice once. */
export const LARGE_BYTES = 25 * 1024 * 1024
export const LARGE_PAGES = 400

export const isLargeDocument = (bytes: number, pageCount: number | null | undefined) =>
  bytes > LARGE_BYTES || (pageCount ?? 0) > LARGE_PAGES
