import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
  Badge,
  BarChart,
  BellRing,
  BookOpen,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Check,
  Checkbox,
  CircleAlert,
  CircleHelp,
  ConfidenceDot,
  Container,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  EmptyState,
  Eye,
  Heatmap,
  Input,
  Kbd,
  KeyRound,
  Label,
  LoaderCircle,
  Logo,
  Mail,
  Menu,
  Moon,
  NumberStepper,
  Popover,
  PopoverContent,
  PopoverTrigger,
  ProgressBar,
  ProgressRing,
  Reveal,
  SegmentedControl,
  SelectField,
  Skeleton,
  Slider,
  Sparkles,
  StatTile,
  StickyStory,
  Sun,
  SunMoon,
  Switch,
  Tabs,
  TabsList,
  TabsTrigger,
  ThemeRadioGroup,
  ThemeSwitcher,
  Timer,
  ToastProvider,
  Tooltip,
  TooltipProvider,
  useTheme,
  useToast,
  X,
} from '@artha/design-system'
import { useState } from 'react'

import { AnnotationPrimitivesShowcase } from './AnnotationPrimitivesShowcase'
import { NewPrimitivesShowcase } from './NewPrimitivesShowcase'
import { NotesPrimitivesShowcase } from './NotesPrimitivesShowcase'
import { RecallPrimitivesShowcase } from './RecallPrimitivesShowcase'

const swatches = [
  ['background', 'bg-background'],
  ['foreground', 'bg-foreground'],
  ['card', 'bg-card'],
  ['primary', 'bg-primary'],
  ['secondary', 'bg-secondary'],
  ['muted', 'bg-muted'],
  ['accent', 'bg-accent'],
  ['highlight', 'bg-highlight'],
  ['destructive', 'bg-destructive'],
  ['border', 'bg-border'],
] as const

const icons = [
  ['BookOpen', BookOpen],
  ['Sun', Sun],
  ['Moon', Moon],
  ['SunMoon', SunMoon],
  ['Timer', Timer],
  ['BellRing', BellRing],
  ['Sparkles', Sparkles],
  ['Mail', Mail],
  ['KeyRound', KeyRound],
  ['Eye', Eye],
  ['Check', Check],
  ['X', X],
  ['Menu', Menu],
  ['CircleAlert', CircleAlert],
  ['LoaderCircle', LoaderCircle],
] as const

function ThemeStatus() {
  const { preference, resolved } = useTheme()
  return (
    <p className="text-sm text-muted-foreground" role="status">
      Preference: <strong className="text-foreground">{preference}</strong>. Painted as:{' '}
      <strong className="text-foreground">{resolved}</strong>.
    </p>
  )
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <h2 className="text-xl font-bold">{title}</h2>
      {children}
    </section>
  )
}

function ControlsDemo() {
  const [n, setN] = useState(3)
  const [rounds, setRounds] = useState('2')
  return (
    <div className="max-w-sm space-y-4">
      <div className="flex items-center gap-3">
        <Checkbox id="demo-check" defaultChecked />
        <Label htmlFor="demo-check">Chapter completed</Label>
      </div>
      <div className="flex items-center gap-3">
        <Switch id="demo-switch" />
        <Label htmlFor="demo-switch">Weighted view</Label>
      </div>
      <div className="space-y-2">
        <Label htmlFor="demo-select">Revision rounds</Label>
        <SelectField
          id="demo-select"
          value={rounds}
          onValueChange={setRounds}
          options={[
            { value: '1', label: '1' },
            { value: '2', label: '2' },
          ]}
        />
      </div>
      <NumberStepper label="Chapters read" value={n} onChange={setN} max={10} />
    </div>
  )
}

const DEMO_COLUMNS = Array.from({ length: 14 }, (_, i) => ({
  label: `Day ${i + 1}`,
  short: String(i + 1),
  values: { reading: ((i * 37) % 60) * 60, practice: ((i * 53) % 45) * 60 },
}))
const DEMO_HEAT = Array.from({ length: 56 }, (_, i) => ({
  date: `2026-09-${String((i % 28) + 1).padStart(2, '0')}-${i}`,
  level: (i * 7) % 6,
  weekday: i % 7,
  label: `Day ${i + 1}: level ${(i * 7) % 6}`,
}))

function FocusTimerDemo() {
  const [volume, setVolume] = useState(70)
  return (
    <TooltipProvider>
      <div className="max-w-md space-y-4">
        <div className="space-y-1">
          <Label>Alert volume: {volume}</Label>
          <Slider label="Alert volume" value={volume} min={0} max={100} step={5} onValueChange={setVolume} />
        </div>
        <p className="text-sm text-muted-foreground">
          Press <Kbd>Space</Kbd> to start or pause, <Kbd>S</Kbd> to skip a break and <Kbd>E</Kbd> to end a round early.
        </p>
        <Tooltip content="Adds five minutes, up to three times">
          <Button variant="outline">+5 min</Button>
        </Tooltip>
      </div>
    </TooltipProvider>
  )
}

function TimeTrackerDemo() {
  const [range, setRange] = useState('30d')
  const toast = useToast()
  return (
    <div className="space-y-6">
      <div className="grid max-w-2xl grid-cols-2 gap-3 sm:grid-cols-3">
        <StatTile label="Total study time" value="12 h 30 m" hint="Up 1 h 10 m on the previous period" />
        <StatTile label="Days studied" value={9} />
        <StatTile label="Best day" value="3 h 05 m" hint="Mon, 5 Oct 2026" />
      </div>
      <SegmentedControl
        label="Range"
        value={range}
        onValueChange={setRange}
        options={[
          { value: '7d', label: '7 days' },
          { value: '30d', label: '30 days' },
          { value: '90d', label: '90 days' },
        ]}
      />
      <div className="max-w-2xl">
        <BarChart
          title="Study time by day"
          series={[
            { key: 'reading', name: 'Reading' },
            { key: 'practice', name: 'Practice' },
          ]}
          columns={DEMO_COLUMNS}
          format={(s) => `${Math.floor(s / 60)} m`}
        />
      </div>
      <div className="max-w-2xl">
        <Heatmap
          title="Study days"
          cells={DEMO_HEAT}
          weekdayLabels={['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']}
          legend={{ less: 'Less', more: 'More' }}
        />
      </div>
      <div className="flex flex-wrap gap-3">
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="outline">Open a dialog</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogTitle>Add study time</DialogTitle>
            <DialogDescription>Focus is trapped here and Escape closes it.</DialogDescription>
          </DialogContent>
        </Dialog>
        <Button
          variant="outline"
          onClick={() =>
            toast.show({ message: 'Deleted 45 m of study time.', actionLabel: 'Undo', onAction: () => {} })
          }
        >
          Show a toast with undo
        </Button>
      </div>
    </div>
  )
}

/** Living style guide for @artha/design-system. Every primitive appears here in all its variants. */
export function DesignShowcase() {
  return (
    <Container className="space-y-12 py-14">
      <header className="space-y-3">
        <Logo />
        <h1 className="text-4xl font-extrabold">Design system</h1>
        <p className="max-w-2xl text-muted-foreground">
          Tokens and primitives from <code>packages/design-system</code>. Use the theme menu in the header to check
          every theme.
        </p>
      </header>

      <Block title="Themes">
        <p className="max-w-2xl text-muted-foreground">
          Reading (default), Light, Dark and System. System shows Light from 6 am to 6 pm and Dark from 6 pm to 6 am
          (device time), and switches by itself while the page is open. Every screen must be checked in all four.
        </p>
        <div className="flex items-center gap-3">
          <ThemeSwitcher />
          <ThemeStatus />
        </div>
        <ThemeRadioGroup className="max-w-xl sm:grid-cols-2" />
      </Block>

      <Block title="Icons (Lucide)">
        <p className="max-w-2xl text-muted-foreground">
          Import from <code>@artha/design-system</code>. Add new icons to <code>src/icons.ts</code>.
        </p>
        <ul className="grid grid-cols-3 gap-3 sm:grid-cols-5">
          {icons.map(([name, Icon]) => (
            <li key={name} className="flex flex-col items-center gap-2 rounded-lg border bg-card p-3 text-center">
              <Icon aria-hidden className="size-5 text-primary" />
              <span className="text-xs">{name}</span>
            </li>
          ))}
        </ul>
      </Block>

      <Block title="Reading typography">
        <article className="prose-reading rounded-xl border bg-card p-6">
          <p>
            Use <code>prose-reading</code> for long-form content such as notes and study material: a serif face,
            generous line height and a comfortable line length of about 68 characters.
          </p>
          <p>It looks the same in every theme and takes its colours from the tokens.</p>
        </article>
      </Block>

      <Block title="Menu">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline">Open menu</Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuItem>Profile</DropdownMenuItem>
            <DropdownMenuItem>Settings</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </Block>

      <Block title="Colour tokens">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {swatches.map(([name, cls]) => (
            <div key={name} className="space-y-2">
              <div className={`h-16 rounded-lg border ${cls}`} />
              <p className="text-xs font-medium">{name}</p>
            </div>
          ))}
        </div>
      </Block>

      <Block title="Typography">
        <div className="space-y-2">
          <p className="font-display text-5xl font-extrabold">Display 5xl</p>
          <p className="font-display text-3xl font-bold">Heading 3xl</p>
          <p className="text-lg">Body large, Inter Variable</p>
          <p className="text-sm text-muted-foreground">Small muted text</p>
        </div>
      </Block>

      <Block title="Buttons">
        <div className="flex flex-wrap items-center gap-3">
          <Button>Default</Button>
          <Button variant="accent">Accent</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="link">Link</Button>
          <Button size="sm">Small</Button>
          <Button size="lg">Large</Button>
          <Button disabled>Disabled</Button>
        </div>
      </Block>

      <Block title="Badges">
        <div className="flex flex-wrap gap-2">
          <Badge>Default</Badge>
          <Badge variant="outline">Outline</Badge>
          <Badge variant="accent">Accent</Badge>
          <Badge variant="highlight">Highlight</Badge>
        </div>
      </Block>

      <Block title="Form">
        <div className="max-w-sm space-y-3">
          <Input placeholder="you@example.com" />
          <Input placeholder="Disabled" disabled />
        </div>
      </Block>

      <Block title="Card">
        <Card className="max-w-sm">
          <CardHeader>
            <CardTitle>Advanced Accounting</CardTitle>
            <CardDescription>68% covered</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">Card content sits here.</CardContent>
        </Card>
      </Block>

      <Block title="Tabs">
        <Tabs defaultValue="ca">
          <TabsList>
            <TabsTrigger value="ca">CA</TabsTrigger>
            <TabsTrigger value="cs">CS</TabsTrigger>
            <TabsTrigger value="cma">CMA</TabsTrigger>
          </TabsList>
        </Tabs>
      </Block>

      <Block title="Accordion">
        <Accordion type="single" collapsible className="max-w-xl">
          <AccordionItem value="a">
            <AccordionTrigger>What is this?</AccordionTrigger>
            <AccordionContent>A primitive built on Radix with our tokens.</AccordionContent>
          </AccordionItem>
        </Accordion>
      </Block>

      <Block title="Progress">
        <div className="flex flex-wrap items-center gap-8">
          <ProgressRing value={68} label="Overall coverage" />
          <ProgressRing value={12} size={64} strokeWidth={6} tone="destructive" label="Needs attention">
            <span className="text-sm font-bold">12%</span>
          </ProgressRing>
          <div className="w-64 space-y-3">
            <ProgressBar value={45} label="Reading" />
            <ProgressBar value={80} size="lg" label="Practice" />
          </div>
        </div>
      </Block>

      <Block title="Time tracker">
        <ToastProvider>
          <TimeTrackerDemo />
        </ToastProvider>
      </Block>

      <Block title="Focus timer">
        <FocusTimerDemo />
      </Block>

      <Block title="Selection controls">
        <ControlsDemo />
      </Block>

      <Block title="Confidence markers">
        <div className="flex flex-wrap gap-4">
          <ConfidenceDot value="red" showLabel />
          <ConfidenceDot value="amber" showLabel />
          <ConfidenceDot value="green" showLabel />
        </div>
      </Block>

      <Block title="Loading and empty states">
        <div className="max-w-sm space-y-2" aria-busy="true">
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-16 w-full" />
        </div>
        <EmptyState title="Nothing due today" description="Revisions you schedule will show up here." />
      </Block>

      <Block title="Breadcrumb and popover">
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>Courses</BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>CA Intermediate</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" size="sm">
              <CircleHelp /> How is this calculated?
            </Button>
          </PopoverTrigger>
          <PopoverContent>Reading 40%, practice 30%, revision 20%, mock 10%.</PopoverContent>
        </Popover>
      </Block>

      <NewPrimitivesShowcase />
      <NotesPrimitivesShowcase />
      <RecallPrimitivesShowcase />
      <AnnotationPrimitivesShowcase />

      <Block title="Motion">
        <Reveal>
          <Card className="max-w-sm p-6">Fades up when it enters the viewport and respects reduced motion.</Card>
        </Reveal>
        <p className="text-sm text-muted-foreground">
          Sticky story: on a wide screen the rail stays put while you scroll; on a phone, or with reduced motion, every
          step stacks.
        </p>
        <StickyStory
          label="Showcase walkthrough"
          stepVh={42}
          steps={[
            {
              id: 'ds-story-plan',
              rail: 'Plan',
              content: (
                <div className="space-y-2">
                  <h3 className="text-xl font-bold">Tell us the attempt</h3>
                  <p className="text-muted-foreground">Course, level and exam date. Under a minute.</p>
                </div>
              ),
              media: <Card className="w-full p-6 text-sm text-muted-foreground">Goal card</Card>,
            },
            {
              id: 'ds-story-today',
              rail: 'Today',
              content: (
                <div className="space-y-2">
                  <h3 className="text-xl font-bold">Follow the list</h3>
                  <p className="text-muted-foreground">Learn, revise, practise — one focused day.</p>
                </div>
              ),
              media: <Card className="w-full p-6 text-sm text-muted-foreground">Today list</Card>,
            },
          ]}
        />
      </Block>
    </Container>
  )
}
