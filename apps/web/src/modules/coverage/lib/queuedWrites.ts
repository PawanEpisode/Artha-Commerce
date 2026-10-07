import { QueuedOffline, writeOrQueue } from '~/lib/offline-queue'

import {
  chapterTickRequest,
  eventRequest,
  logEvent,
  newClientId,
  tickChapter,
  tickTopic,
  topicTickRequest,
} from './api'
import type { ChapterState, EventType } from './types'

/** Tick (or untick) a topic. Returns null when the write was queued for later. */
export async function tickTopicOrQueue(topicId: string, done: boolean): Promise<ChapterState | null> {
  const id = newClientId()
  const { method, path, body } = topicTickRequest(topicId, done, id)
  return orNull(writeOrQueue({ clientId: id, method, path, body }, () => tickTopic(topicId, done, id)))
}

export async function tickChapterOrQueue(chapterId: string, done: boolean): Promise<ChapterState | null> {
  const id = newClientId()
  const { method, path, body } = chapterTickRequest(chapterId, done, id)
  return orNull(writeOrQueue({ clientId: id, method, path, body }, () => tickChapter(chapterId, done, id)))
}

export async function logEventOrQueue(input: {
  chapter_id: string
  type: EventType
  value?: number | null
  /** Chapter name, kept with a queued write for the "skipped" message. */
  label?: string
}): Promise<ChapterState | null> {
  const id = newClientId()
  const { label, ...fields } = input
  const request = { ...fields, value: input.value ?? null, client_id: id }
  const { method, path, body } = eventRequest(request)
  return orNull(writeOrQueue({ clientId: id, method, path, body, label }, () => logEvent(request)))
}

async function orNull<T>(write: Promise<T>): Promise<T | null> {
  try {
    return await write
  } catch (error) {
    if (error instanceof QueuedOffline) return null
    throw error
  }
}
