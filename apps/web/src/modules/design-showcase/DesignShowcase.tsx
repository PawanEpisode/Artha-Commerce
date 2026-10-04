import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
  Badge,
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  EmptyState,
  Eye,
  Input,
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
  Select,
  Skeleton,
  Sparkles,
  Sun,
  SunMoon,
  Switch,
  Tabs,
  TabsList,
  TabsTrigger,
  ThemeRadioGroup,
  ThemeSwitcher,
  Timer,
  useTheme,
  X,
} from '@artha/design-system'
import { useState } from 'react'

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
        <Select id="demo-select" defaultValue="2">
          <option value="1">1</option>
          <option value="2">2</option>
        </Select>
      </div>
      <NumberStepper label="Chapters read" value={n} onChange={setN} max={10} />
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

      <Block title="Motion">
        <Reveal>
          <Card className="max-w-sm p-6">Fades up when it enters the viewport and respects reduced motion.</Card>
        </Reveal>
      </Block>
    </Container>
  )
}
