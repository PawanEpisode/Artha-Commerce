import { Alert, Button, EmptyState, Skeleton, Trash2 } from '@artha/design-system'
import { useState } from 'react'

import { useOnline } from '~/modules/personalization'

import { TrashList } from '../components/TrashList'
import { useNoteActions } from '../hooks/useNoteActions'
import { flattenPages, useNoteList } from '../hooks/useNotesQueries'
import { NotesShell } from './NotesShell'

function Trash() {
  const online = useOnline()
  const actions = useNoteActions()
  const list = useNoteList({ trashed: true, limit: 30 })
  const { items } = flattenPages(list.data?.pages)
  const [restoringId, setRestoringId] = useState<string>()

  return (
    <>
      <header className="space-y-1">
        <h1 className="font-display text-3xl font-extrabold">Trash</h1>
        <p className="text-muted-foreground">Deleted notes stay here for 30 days, then they are removed for good.</p>
      </header>
      {list.isPending ? (
        <div aria-busy="true" className="space-y-3">
          <span role="status" className="sr-only">
            Loading the trash…
          </span>
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : list.isError ? (
        <Alert variant="error">
          <span className="flex flex-wrap items-center gap-3">
            <span>We could not load the trash.</span>
            <Button size="sm" variant="outline" onClick={() => void list.refetch()}>
              Try again
            </Button>
          </span>
        </Alert>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Trash2 aria-hidden />}
          title="The trash is empty"
          description="Notes you delete will wait here for 30 days."
        />
      ) : (
        <div className="space-y-3">
          {!online ? (
            <Alert variant="info">
              <span>You are offline. You can restore notes when you are back online.</span>
            </Alert>
          ) : null}
          <TrashList
            items={items}
            online={online}
            restoringId={restoringId}
            onRestore={async (note) => {
              setRestoringId(note.id)
              await actions.restore(note)
              setRestoringId(undefined)
            }}
          />
          {list.hasNextPage ? (
            <Button variant="outline" disabled={list.isFetchingNextPage} onClick={() => void list.fetchNextPage()}>
              {list.isFetchingNextPage ? 'Loading…' : 'Load more'}
            </Button>
          ) : null}
        </div>
      )}
    </>
  )
}

export function NotesTrashContainer() {
  return (
    <NotesShell width="max-w-3xl">
      <Trash />
    </NotesShell>
  )
}
