import { Switch } from '@artha/design-system'

import type { Channel, NotificationCategory, PreferenceChange } from '../lib/schemas'

const CHANNEL_LABEL: Record<Channel, string> = { push: 'Push', email: 'Email', inbox: 'Inbox' }
const CHANNEL_ORDER: readonly Channel[] = ['push', 'email', 'inbox']

/**
 * What to be told about, and where: one group per category with a labelled switch per channel. Each switch saves on
 * its own. Group and switch names are spoken in full ("Timer alerts, Push") so a screen reader never hears a bare "Push".
 */
export function CategoryGrid({
  categories,
  onChange,
}: {
  categories: readonly NotificationCategory[]
  onChange: (change: PreferenceChange) => void
}) {
  return (
    <ul className="divide-y divide-border">
      {categories.map((category) => (
        <li key={category.key} className="py-4 first:pt-0 last:pb-0">
          <fieldset className="min-w-0 space-y-3">
            <legend className="text-sm font-semibold">{category.label}</legend>
            <p className="text-sm text-muted-foreground">{category.description}</p>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              {CHANNEL_ORDER.map((channel) => {
                const id = `pref-${category.key}-${channel}`
                return (
                  <div key={channel} className="flex items-center gap-2">
                    <Switch
                      id={id}
                      aria-label={`${category.label}, ${CHANNEL_LABEL[channel]}`}
                      checked={category.channels[channel]}
                      onCheckedChange={(enabled) => onChange({ category: category.key, channel, enabled })}
                    />
                    {/* The visible text is a label too, so a tap on it toggles; aria-label above names it in full. */}
                    <label htmlFor={id} className="min-h-11 content-center text-sm">
                      {CHANNEL_LABEL[channel]}
                    </label>
                  </div>
                )
              })}
            </div>
          </fieldset>
        </li>
      ))}
    </ul>
  )
}
