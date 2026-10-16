import { Button, Label, Pin, RefreshCw, Switch, TriangleAlert } from '@artha/design-system'

import { bannerHelp, bannerTitle } from '../lib/updates'

interface BannerProps {
  changes: number
  follow: boolean
  onReview: () => void
}

/** "Update available" on a deck she has: what it is and the way to look before she applies. */
export function UpdateBanner({ changes, follow, onReview }: BannerProps) {
  return (
    <section
      aria-label="Deck update"
      className="space-y-2 rounded-lg border border-input bg-secondary p-3 text-[13px] text-foreground"
    >
      <p className="flex items-center gap-2 font-semibold">
        <RefreshCw aria-hidden className="size-4 text-primary" />
        {bannerTitle(changes)}
      </p>
      <p className="text-muted-foreground">{bannerHelp(follow)}</p>
      <Button size="sm" onClick={onReview}>
        See what changed
      </Button>
    </section>
  )
}

interface FollowProps {
  follow: boolean
  pending: boolean
  disabled?: boolean
  onChange: (follow: boolean) => void
}

/** Follow (the default) takes updates by itself; pin keeps her cards exactly as they are until she applies. */
export function FollowToggle({ follow, pending, disabled, onChange }: FollowProps) {
  return (
    <div className="flex items-start gap-3">
      <Switch
        id="follow-updates"
        checked={follow}
        disabled={pending || disabled}
        onCheckedChange={onChange}
        aria-describedby="follow-updates-help"
      />
      <div className="min-w-0 space-y-0.5">
        <Label htmlFor="follow-updates" className="flex items-center gap-1.5 text-[13px] font-medium">
          {follow ? null : <Pin aria-hidden className="size-4" />}
          Take updates automatically
        </Label>
        <p id="follow-updates-help" className="text-xs text-muted-foreground">
          {follow
            ? 'New versions of this deck are applied for you. Cards whose meaning changed come back for a re-check.'
            : 'Pinned: your cards stay as they are until you choose to update.'}
        </p>
      </div>
    </div>
  )
}

/** Shown on a deck written for the previous syllabus (the student changed scheme). */
export function OldSyllabusFlag() {
  return (
    <p className="flex items-start gap-2 text-xs text-muted-foreground">
      <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
      <span>
        This deck is for the old syllabus. Its cards are kept, but the chapters may not match your new syllabus.
      </span>
    </p>
  )
}
