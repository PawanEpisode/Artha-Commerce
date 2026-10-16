import {
  Badge,
  BookOpen,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  type CommandItem,
  CommandPalette,
  DataTable,
  EmptyState,
  FilterChip,
  Input,
  Kbd,
  Page,
  PageHeader,
  Search,
  SectionTabs,
  SelectField,
  SidebarGroup,
  SidebarItem,
  SidebarProvider,
  Sparkles,
  StatTile,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableToolbar,
  Tabs,
  TabsList,
  TabsTrigger,
  Timer,
  toast,
} from '@artha/design-system'
import { useState } from 'react'

const COMMANDS: CommandItem[] = [
  { id: 'today', label: 'Today', group: 'Plan', icon: Timer, hint: 'G T' },
  { id: 'notes', label: 'Notes', group: 'Learn', icon: BookOpen, keywords: ['pdf', 'library'] },
  { id: 'ai', label: 'Ask the tutor', group: 'Learn', icon: Sparkles },
]

const ROWS = [
  { id: 'q1', title: 'AS 19 Leases: lessor classification', paper: 'Advanced Accounting', status: 'Done', marks: 14 },
  { id: 'q2', title: 'GST input tax credit: blocked credits', paper: 'Taxation', status: 'Revise', marks: 8 },
  { id: 'q3', title: 'Charges: registration with the ROC', paper: 'Corporate Law', status: 'New', marks: 6 },
]

function Row({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </div>
  )
}

function CommandDemo() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        <Search aria-hidden /> Jump to <Kbd aria-hidden>Ctrl K</Kbd>
      </Button>
      <CommandPalette
        open={open}
        onOpenChange={setOpen}
        items={COMMANDS}
        onSelect={(item) => {
          setOpen(false)
          toast.success(`Selected ${item.label}`)
        }}
      />
    </>
  )
}

function TableDemo() {
  const [paper, setPaper] = useState('all')
  const [filtered, setFiltered] = useState(true)
  const rows = ROWS.filter((r) => paper === 'all' || r.paper === paper)
  return (
    <div className="space-y-3">
      <TableToolbar>
        <Input aria-label="Search questions" placeholder="Search questions" />
        <SelectField
          aria-label="Paper"
          value={paper}
          onValueChange={setPaper}
          options={[
            { value: 'all', label: 'All papers' },
            { value: 'Taxation', label: 'Taxation' },
            { value: 'Corporate Law', label: 'Corporate Law' },
          ]}
        />
        {filtered ? (
          <FilterChip removeLabel="Remove filter Unattempted" onRemove={() => setFiltered(false)}>
            Unattempted
          </FilterChip>
        ) : null}
      </TableToolbar>
      <DataTable>
        <TableHeader>
          <TableRow>
            <TableHead>Question</TableHead>
            <TableHead className="hidden md:table-cell">Paper</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Marks</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.id}>
              <TableCell className="font-medium">{r.title}</TableCell>
              <TableCell className="hidden text-muted-foreground md:table-cell">{r.paper}</TableCell>
              <TableCell>
                <Badge variant={r.status === 'Done' ? 'accent' : 'outline'}>{r.status}</Badge>
              </TableCell>
              <TableCell className="text-right tabular-nums">{r.marks}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </DataTable>
    </div>
  )
}

/** The compact (Linear-style) scale: button sizes, Page, PageHeader, DataTable, Sidebar items, the command palette. */
export function CompactShowcase() {
  const [tab, setTab] = useState('overview')
  return (
    <>
      <section className="space-y-4">
        <h2 className="text-base font-semibold">Button sizes</h2>
        <p className="max-w-2xl text-sm text-muted-foreground">
          24, 28 and 32 px with a mouse; 36 to 44 px on touch screens (<code>pointer-coarse:</code>). <code>lg</code>{' '}
          and <code>xl</code> are for public pages only.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Button size="xs">xs</Button>
          <Button size="sm">sm</Button>
          <Button>default</Button>
          <Button size="lg">lg</Button>
          <Button size="xl">xl</Button>
          <Button size="icon" aria-label="Icon button">
            <Sparkles />
          </Button>
          <Button size="icon-sm" variant="outline" aria-label="Small icon button">
            <Sparkles />
          </Button>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-base font-semibold">Page, PageHeader and StatTile</h2>
        <div className="rounded-lg border bg-background">
          <Page>
            <PageHeader
              eyebrow="Plan"
              title="Study plan"
              description="Hours and chapters until your exam."
              actions={
                <>
                  <Button variant="outline" size="sm">
                    Export
                  </Button>
                  <Button>New plan</Button>
                </>
              }
            />
            <div className="grid gap-3 sm:grid-cols-3">
              <StatTile label="This week" value="14 h 20 m" hint="2 h more than last week" />
              <StatTile label="Coverage" value="68%" hint="41 of 60 chapters" />
              <StatTile label="Streak" value="12 days" />
            </div>
          </Page>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-base font-semibold">DataTable with toolbar</h2>
        <TableDemo />
        <EmptyState
          icon={<Search />}
          title="No questions match"
          description="Clear a filter to see more."
          action={
            <Button size="sm" variant="outline">
              Clear filters
            </Button>
          }
        />
      </section>

      <section className="space-y-4">
        <h2 className="text-base font-semibold">Sidebar items and Jump-to</h2>
        <p className="max-w-2xl text-sm text-muted-foreground">
          The real <code>Sidebar</code> is fixed to the viewport, so only its items are shown here, inside a box.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <SidebarProvider>
            <div className="w-56 rounded-lg border bg-sidebar p-2">
              <SidebarGroup label="Plan">
                <SidebarItem icon={Timer} data-active="true">
                  Today
                </SidebarItem>
                <SidebarItem icon={BookOpen} trailing="12">
                  Notes
                </SidebarItem>
              </SidebarGroup>
            </div>
          </SidebarProvider>
          <Row title="Command palette">
            <CommandDemo />
          </Row>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-base font-semibold">Compact Card, Tabs, SectionTabs, Select and Input</h2>
        <div className="grid gap-3 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Advanced Accounting</CardTitle>
              <CardDescription>68% covered</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap items-center gap-2">
              <Badge>Group I</Badge>
              <Badge variant="outline">Paper 1</Badge>
              <Badge variant="highlight">Revise</Badge>
            </CardContent>
          </Card>
          <div className="space-y-3">
            <Tabs defaultValue="ca">
              <TabsList>
                <TabsTrigger value="ca">CA</TabsTrigger>
                <TabsTrigger value="cs">CS</TabsTrigger>
                <TabsTrigger value="cma">CMA</TabsTrigger>
              </TabsList>
            </Tabs>
            <SectionTabs
              label="Showcase sections"
              variant="tablist"
              value={tab}
              onValueChange={setTab}
              items={[
                { value: 'overview', label: 'Overview' },
                { value: 'reports', label: 'Reports' },
                { value: 'goals', label: 'Goals' },
              ]}
            />
            <div className="flex flex-wrap gap-2">
              <Input aria-label="Compact input" placeholder="Compact input" className="max-w-48" />
              <SelectField
                aria-label="Compact select"
                value="2"
                onValueChange={() => undefined}
                options={[
                  { value: '1', label: 'One round' },
                  { value: '2', label: 'Two rounds' },
                ]}
              />
            </div>
          </div>
        </div>
      </section>
    </>
  )
}
