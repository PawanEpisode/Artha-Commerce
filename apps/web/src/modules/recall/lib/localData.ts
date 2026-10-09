import { registerLocalDataClearer } from '~/lib/local-data'

import { cardEditQueue } from './cardEditQueue'
import { cardQueue } from './cardQueue'
import { eventStore } from './eventStore'

/** Everything recall keeps on this device for one student: the offline pack and review events, queued new cards and edits. */
export async function clearRecallLocalData(userId: string): Promise<void> {
  for (const entry of cardQueue.list(userId)) cardQueue.remove(userId, entry.body.client_id)
  for (const entry of cardEditQueue.list(userId)) cardEditQueue.remove(userId, entry.cardId)
  await eventStore.clear()
}

registerLocalDataClearer('recall', clearRecallLocalData)
