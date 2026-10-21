import React from 'react'

import { ItemDetail } from '../components/ItemDetail'
import { useItemDetail } from '../hooks/useItemDetail'

interface ItemContainerProps {
  itemId: string
  onBack: () => void
}

export const ItemContainer: React.FC<ItemContainerProps> = ({ itemId, onBack }) => {
  const { item, isLoading, error, setProgress, report } = useItemDetail(itemId)

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl animate-pulse space-y-6 p-4 sm:p-8">
        <div className="h-64 rounded-3xl bg-muted/40" />
      </div>
    )
  }

  if (error || !item) {
    return (
      <div className="mx-auto max-w-md space-y-4 p-8 text-center">
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          Failed to load study material item.
        </div>
        <button
          type="button"
          onClick={onBack}
          className="min-h-[44px] rounded-xl border px-4 py-2 text-sm font-semibold"
        >
          Go Back
        </button>
      </div>
    )
  }

  return (
    <ItemDetail
      item={item}
      onStateChange={setProgress}
      onReport={async (payload) => {
        await report(payload)
      }}
      onBack={onBack}
    />
  )
}
