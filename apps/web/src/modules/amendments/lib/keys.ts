export const amendmentsKeys = {
  all: ['amendments'] as const,
  summary: () => [...amendmentsKeys.all, 'summary'] as const,
  cards: (filter?: Record<string, unknown>, cursor?: string | null) =>
    [...amendmentsKeys.all, 'cards', filter ?? {}, cursor ?? ''] as const,
  cardDetail: (publicId: string) => [...amendmentsKeys.all, 'card', publicId] as const,
  archive: () => [...amendmentsKeys.all, 'archive'] as const,
  chapter: (chapterId: string) => [...amendmentsKeys.all, 'chapter', chapterId] as const,
}
