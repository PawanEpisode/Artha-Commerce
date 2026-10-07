import { keepPreviousData, useInfiniteQuery, useQueries, useQuery } from '@tanstack/react-query'

import { currentUserId, isTransient } from '~/lib/offline-queue'
import { useOverview } from '~/modules/coverage'

import {
  getAggregate,
  getCounts,
  getNote,
  getOverview,
  getUsage,
  getVersion,
  listChanges,
  listNotes,
  listTags,
  listVersions,
  searchNotes,
  suggestChapters,
} from '../lib/api'
import type { AggregateParams } from '../lib/filter-schema'
import { notesKeys } from '../lib/keys'
import { filterCached, type LocalFilter, toSummary } from '../lib/local-filter'
import { cachedNotes, cacheNote, readCachedNote } from '../lib/offline-store'
import type { AggregateItem, Note, NoteSummary, Page, SearchHit } from '../lib/types'

/** The level of the student's active enrolment: notes views are scoped to it (subject and chapter keys need a level). */
export function useLevelId(): string | undefined {
  return useOverview().data?.enrollment.level.id
}

/** The subjects of the enrolment (id, key, name), the source of the hub's subject list and the picker. */
export function useEnrolledSubjects() {
  const { data, isPending, isError, refetch, noEnrollment } = useOverview()
  return {
    noEnrollment,
    subjects: data?.subjects.map((s) => ({ id: s.id, key: s.key, name: s.name })) ?? [],
    isPending,
    isError,
    refetch,
  }
}

const localFilterOf = (params: AggregateParams): LocalFilter => ({
  subject: params.subject,
  chapter: params.chapter,
  topic: params.topic,
  unfiled: params.unfiled,
  q: params.q,
  search: { tag: params.tag, from: params.from, to: params.to },
})

/** What the device still holds when the network is gone: the notes opened recently, filtered the way the server would. */
async function offlineAggregate(params: AggregateParams): Promise<Page<AggregateItem> & { offline: true }> {
  const userId = await currentUserId()
  // Highlights and documents only exist online (R2); typed notes are what the cache holds.
  const notes = userId && (params.tab === 'all' || params.tab === 'notes') ? await cachedNotes(userId) : []
  const items = filterCached(notes, localFilterOf(params)).map((n) => ({ ...toSummary(n), type: 'note' as const }))
  return { items, next_cursor: null, offline: true }
}

export type AggregatePage = Page<AggregateItem> & { offline?: true }

/** The subject or chapter list, a page at a time. Falls back to offline copies when the network is unreachable. */
export function useAggregateList(params: AggregateParams, enabled = true) {
  return useInfiniteQuery({
    queryKey: notesKeys.aggregate({ ...params, cursor: undefined }),
    queryFn: async ({ pageParam }): Promise<AggregatePage> => {
      try {
        return await getAggregate({ ...params, cursor: pageParam })
      } catch (error) {
        if (!isTransient(error)) throw error
        return offlineAggregate(params)
      }
    },
    initialPageParam: params.cursor,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    placeholderData: keepPreviousData,
    enabled: enabled && params.level !== '',
  })
}

export type NoteListPage = Page<NoteSummary> & { offline?: true }

/** Notes lists a page at a time (hub, trash, unfiled inbox). Offline copies stand in when the network is gone. */
export function useNoteList(
  params: { level?: string; unfiled?: boolean; pinned?: boolean; trashed?: boolean; limit?: number },
  enabled = true,
) {
  return useInfiniteQuery({
    queryKey: notesKeys.list(params),
    enabled,
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last: NoteListPage) => last.next_cursor ?? undefined,
    queryFn: async ({ pageParam }): Promise<NoteListPage> => {
      try {
        return await listNotes({ ...params, cursor: pageParam })
      } catch (error) {
        if (!isTransient(error)) throw error
        const userId = await currentUserId()
        const all = userId ? await cachedNotes(userId) : []
        const items = params.trashed
          ? []
          : filterCached(all, { unfiled: params.unfiled, pinned: params.pinned })
              .slice(0, params.limit ?? 30)
              .map(toSummary)
        return { items: items.map((n) => ({ ...n, offline_copy: true })), next_cursor: null, offline: true }
      }
    },
  })
}

/** All items of the pages loaded so far, and whether the last page came from this device. */
export function flattenPages<T>(pages: ReadonlyArray<Page<T> & { offline?: true }> | undefined) {
  return { items: pages?.flatMap((p) => p.items) ?? [], offline: pages?.some((p) => p.offline) ?? false }
}

/** A note, from the server when reachable (and cached for offline), else from the copy on this device. */
export function useNote(id: string, enabled = id !== '') {
  return useQuery({
    enabled,
    queryKey: notesKeys.note(id),
    queryFn: async (): Promise<Note> => {
      const userId = await currentUserId()
      try {
        const note = await getNote(id)
        if (userId) await cacheNote(userId, note)
        return note
      } catch (error) {
        if (!isTransient(error) || !userId) throw error
        const cached = await readCachedNote(userId, id)
        if (!cached) throw error
        return { ...cached.note, offline_copy: true }
      }
    },
  })
}

export const useSubjectCounts = (subject: string, enabled = true) => {
  const level = useLevelId()
  return useQuery({
    queryKey: notesKeys.counts(subject),
    queryFn: () => getCounts(level ?? '', subject),
    enabled: enabled && !!level && subject !== '',
  })
}

/** Counts for several subjects in parallel (the hub). A subject whose request fails reads as unknown, never as zero. */
export function useAllSubjectCounts(subjectKeys: string[]) {
  const level = useLevelId()
  return useQueries({
    queries: subjectKeys.map((subject) => ({
      queryKey: notesKeys.counts(subject),
      queryFn: () => getCounts(level ?? '', subject),
      enabled: !!level,
    })),
  })
}

/** The chapter page slot: counts, the current summary and recent notes of one chapter. */
export function useChapterNotesOverview(subjectKey: string, chapterKey: string, enabled = true) {
  const level = useLevelId()
  return useQuery({
    queryKey: notesKeys.overview(level ?? '', subjectKey, chapterKey),
    queryFn: () => getOverview(level ?? '', subjectKey, chapterKey),
    enabled: enabled && !!level && subjectKey !== '' && chapterKey !== '',
  })
}

export const useTags = () => useQuery({ queryKey: notesKeys.tags, queryFn: listTags })
export const useUsage = () => useQuery({ queryKey: notesKeys.usage, queryFn: getUsage })
export const useVersions = (id: string, enabled = true) =>
  useQuery({ queryKey: notesKeys.versions(id), queryFn: () => listVersions(id), enabled })
export const useVersion = (id: string, rev: number | undefined) =>
  useQuery({
    queryKey: notesKeys.version(id, rev ?? 0),
    queryFn: () => getVersion(id, rev ?? 0),
    enabled: rev !== undefined,
  })

export type SearchPage = Page<SearchHit> & { offline?: true }

/** Search from the server; with no network, a plain text match over the notes kept on this device. */
export function useSearchNotes(params: { q: string; scope?: string; subject?: string; chapter?: string }) {
  const level = useLevelId()
  return useInfiniteQuery({
    queryKey: notesKeys.search({ ...params, level }),
    queryFn: async ({ pageParam }): Promise<SearchPage> => {
      try {
        return await searchNotes({
          ...params,
          level: params.subject ? level : undefined,
          cursor: pageParam,
          limit: 20,
        })
      } catch (error) {
        if (!isTransient(error)) throw error
        const userId = await currentUserId()
        const notes = userId ? await cachedNotes(userId) : []
        const items = filterCached(notes, { q: params.q, subject: params.subject, chapter: params.chapter }).map(
          (n, index): SearchHit => ({
            type: 'note',
            id: n.id,
            title: n.title,
            snippet: n.snippet,
            link: n.link,
            rank: index,
            updated_at: n.updated_at,
          }),
        )
        return { items, next_cursor: null, offline: true }
      }
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last: SearchPage) => last.next_cursor ?? undefined,
    enabled: params.q.trim() !== '',
    placeholderData: keepPreviousData,
  })
}

/** One tap suggestions for an unfiled note: a pure text match on the server (no AI). */
export function useChapterSuggestions(noteId: string, text: string, enabled: boolean) {
  const level = useLevelId()
  return useQuery({
    queryKey: notesKeys.suggest(noteId),
    queryFn: () => suggestChapters(text, level),
    enabled: enabled && text.trim().length >= 3,
    staleTime: 5 * 60_000,
  })
}

/** The first page of the changes feed, which the offline cache can be topped up from. */
export const useChangesFeed = (enabled: boolean) =>
  useQuery({ queryKey: [...notesKeys.all, 'changes'], queryFn: () => listChanges(), enabled, staleTime: 5 * 60_000 })
