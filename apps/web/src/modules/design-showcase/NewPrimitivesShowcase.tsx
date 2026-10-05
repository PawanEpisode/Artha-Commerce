import {
  AlarmClock,
  Button,
  ButtonLink,
  DurationField,
  EntityBadge,
  EntityDot,
  EntityRow,
  formatDuration,
  PartyPopper,
  ReadToggle,
  SectionTabs,
  StudyTimeIcon,
  toast,
  toastApiError,
  Trash2,
  Upload,
} from '@artha/design-system'
import { useState } from 'react'

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <h2 className="text-xl font-bold">{title}</h2>
      {children}
    </section>
  )
}

const tabs = [
  { value: 'today', label: 'Today', href: '#today' },
  { value: 'reports', label: 'Reports', href: '#reports' },
  { value: 'log', label: 'Log', href: '#log' },
  { value: 'goals', label: 'Goals', href: '#goals' },
  { value: 'focus', label: 'Focus timer', href: '#focus', icon: StudyTimeIcon },
  { value: 'settings', label: 'Settings', href: '#settings' },
]

function ToastDemo() {
  return (
    <div className="flex flex-wrap gap-2">
      <Button variant="outline" onClick={() => toast.success('Goals saved')}>
        Success
      </Button>
      <Button
        variant="outline"
        onClick={() =>
          toast.error('Could not save', { description: 'Check your connection and try again.', id: 'demo-error' })
        }
      >
        Error (deduped)
      </Button>
      <Button
        variant="outline"
        onClick={() => toast.warning('Target nearly reached', { description: '1 mock test left.' })}
      >
        Warning
      </Button>
      <Button variant="outline" onClick={() => toast.info('Syncing in the background')}>
        Info
      </Button>
      <Button
        variant="outline"
        onClick={() =>
          toast.success('Session deleted', { action: { label: 'Undo', onClick: () => toast.info('Restored') } })
        }
      >
        With Undo
      </Button>
      <Button
        variant="outline"
        onClick={() =>
          toast.custom('All set, welcome aboard', { icon: <PartyPopper className="size-5" aria-hidden /> })
        }
      >
        Custom
      </Button>
      <Button
        variant="outline"
        onClick={() =>
          void toast
            .promise(new Promise((resolve) => setTimeout(resolve, 1500)), {
              loading: 'Saving…',
              success: 'Saved',
              error: 'Failed',
            })
            .catch(() => undefined)
        }
      >
        Promise
      </Button>
      <Button
        variant="outline"
        onClick={() =>
          toastApiError(
            { status: 409, body: { error: { message: 'Mock test target already met.' } } },
            'Something went wrong',
          )
        }
      >
        API error
      </Button>
      <Button variant="ghost" onClick={() => toast.dismiss()}>
        Dismiss all
      </Button>
    </div>
  )
}

function DurationDemo() {
  const [a, setA] = useState<number | null>(90)
  const [b, setB] = useState<number | null>(null)
  return (
    <div className="grid gap-6 sm:grid-cols-2">
      <DurationField
        label="Daily goal"
        valueMinutes={a}
        onChangeMinutes={setA}
        hint={`Stored as ${a ?? '—'} minutes (${a === null ? 'empty' : formatDuration(a, 'long')}).`}
      />
      <DurationField
        size="compact"
        label="Round length (compact, empty)"
        valueMinutes={b}
        onChangeMinutes={setB}
        maxMinutes={240}
      />
      <DurationField
        label="With error"
        valueMinutes={0}
        onChangeMinutes={() => undefined}
        error="Enter at least 5 minutes."
      />
      <DurationField label="Disabled" valueMinutes={45} onChangeMinutes={() => undefined} disabled />
    </div>
  )
}

function ReadDemo() {
  const [read, setRead] = useState(false)
  const [pending, setPending] = useState(false)
  return (
    <div className="flex flex-wrap items-center gap-3">
      <ReadToggle
        checked={read}
        pending={pending}
        onChange={(next) => {
          setRead(next)
          setPending(true)
          setTimeout(() => setPending(false), 800)
        }}
      />
      <ReadToggle checked={false} onChange={() => undefined} disabled />
      <ReadToggle checked onChange={() => undefined} />
    </div>
  )
}

function TabsDemo() {
  const [link, setLink] = useState('today')
  const [panel, setPanel] = useState('a')
  return (
    <div className="space-y-6">
      <div className="max-w-sm overflow-hidden rounded-xl border border-border">
        <SectionTabs
          label="Tracker sections (link tabs, 384px wide)"
          items={tabs}
          value={link}
          sticky={false}
          renderLink={(item, { children, ...props }) => (
            <a href={item.href} {...props} onClick={() => setLink(item.value)}>
              {children}
            </a>
          )}
        />
      </div>
      <SectionTabs
        label="Panels"
        variant="tablist"
        value={panel}
        onValueChange={setPanel}
        sticky={false}
        items={[
          { value: 'a', label: 'Overview' },
          { value: 'b', label: 'Details' },
          { value: 'c', label: 'Disabled', disabled: true },
        ]}
      />
    </div>
  )
}

export function NewPrimitivesShowcase() {
  return (
    <>
      <Block title="Call-to-action buttons">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="cta" size="lg" arrow>
            Start a focus round
          </Button>
          <Button variant="cta" size="xl" arrow>
            Open my coverage
          </Button>
          <Button variant="outline" size="lg">
            Browse the syllabus
          </Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button loading>Saving</Button>
          <Button variant="cta" loading>
            Logging
          </Button>
          <Button disabled>Disabled</Button>
          <Button variant="outline" size="sm">
            <Trash2 /> Remove
          </Button>
          <Button size="lg">
            <Upload /> Upload
          </Button>
        </div>
        <div className="flex max-w-sm flex-col gap-3">
          <Button variant="cta" size="lg" fullWidth arrow>
            Full width CTA
          </Button>
          <ButtonLink href="#cta" variant="outline" size="lg" fullWidth arrow>
            ButtonLink (anchor)
          </ButtonLink>
          <ButtonLink asChild variant="secondary">
            <a href="#cta">
              <AlarmClock /> ButtonLink asChild
            </a>
          </ButtonLink>
        </div>
      </Block>

      <Block title="Section tabs (sticky sub-navigation)">
        <TabsDemo />
      </Block>

      <Block title="Duration field (hours + minutes)">
        <DurationDemo />
      </Block>

      <Block title="Entity badges and tinted rows">
        <div className="flex flex-wrap gap-2">
          <EntityBadge kind="chapter" />
          <EntityBadge kind="topic" />
          <EntityBadge kind="paper" />
          <EntityBadge kind="subject">Cost Accounting</EntityBadge>
          <EntityBadge kind="level">Final</EntityBadge>
          <EntityBadge kind="chapter" size="lg">
            Chapter 4
          </EntityBadge>
          <EntityBadge kind="topic" icon={false}>
            No icon
          </EntityBadge>
        </div>
        <div className="max-w-md space-y-2">
          {(['chapter', 'topic', 'paper'] as const).map((kind) => (
            <EntityRow key={kind} kind={kind} className="flex items-center gap-3">
              <EntityDot kind={kind} />
              <span className="min-w-0 flex-1 truncate font-medium">Sample {kind} row</span>
              <EntityBadge kind={kind} />
            </EntityRow>
          ))}
        </div>
      </Block>

      <Block title="Read toggle">
        <ReadDemo />
      </Block>

      <Block title="Toasts">
        <ToastDemo />
        <p className="text-sm text-muted-foreground">
          Study Time Tracker icon: <StudyTimeIcon className="inline size-4" aria-hidden /> (Flame stays for streaks).
        </p>
      </Block>
    </>
  )
}
