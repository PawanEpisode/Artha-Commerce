import { Building2, Check, Star } from '@artha/design-system'
import React from 'react'

import type { Provider, UserProviderFollow } from '../lib/types'

interface ProviderPickerProps {
  providers: Provider[]
  followed: UserProviderFollow[]
  onFollow: (providerId: string, isPrimary?: boolean) => Promise<void>
  onUnfollow: (userProviderId: string) => Promise<void>
}

export const ProviderPicker: React.FC<ProviderPickerProps> = ({ providers, followed, onFollow, onUnfollow }) => {
  const followedMap = new Map(followed.map((f) => [f.provider_id, f]))

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h3 className="text-sm font-bold text-foreground">Followed Institutes & Providers</h3>
        <p className="text-xs text-muted-foreground">
          Follow your professional accounting bodies to automatically align your study material, editions, and chapter
          checklists.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {providers.map((provider) => {
          const followRecord = followedMap.get(provider.id)
          const isFollowed = Boolean(followRecord)
          const isPrimary = followRecord?.is_primary

          return (
            <div
              key={provider.id}
              className={`flex flex-col justify-between gap-3 rounded-2xl border p-4 transition-all ${
                isFollowed ? 'border-primary/30 bg-primary/5' : 'bg-card'
              }`}
            >
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-muted text-xs font-bold text-foreground">
                      <Building2 className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5 text-sm font-bold text-foreground">
                        {provider.name}
                        {isPrimary && (
                          <span className="inline-flex items-center gap-1 rounded-md bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">
                            <Star className="h-2.5 w-2.5 fill-current" /> Primary
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">{provider.country}</div>
                    </div>
                  </div>
                </div>
                <p className="line-clamp-2 text-xs text-muted-foreground">{provider.full_name}</p>
              </div>

              <div className="flex items-center justify-between gap-2 border-t pt-3">
                {isFollowed && !isPrimary && (
                  <button
                    type="button"
                    onClick={() => onFollow(provider.id, true)}
                    className="min-h-[36px] text-xs font-medium text-muted-foreground hover:text-foreground"
                  >
                    Set as Primary
                  </button>
                )}

                <div className="ml-auto">
                  {isFollowed ? (
                    <button
                      type="button"
                      onClick={() => followRecord && onUnfollow(followRecord.id)}
                      className="inline-flex min-h-[36px] items-center gap-1 rounded-xl border border-rose-200 px-3 py-1.5 text-xs font-semibold text-rose-600 hover:bg-rose-50"
                    >
                      <Check className="h-3.5 w-3.5" />
                      Following
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => onFollow(provider.id, false)}
                      className="min-h-[36px] rounded-xl bg-foreground px-3.5 py-1.5 text-xs font-semibold text-background hover:opacity-90"
                    >
                      Follow
                    </button>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
