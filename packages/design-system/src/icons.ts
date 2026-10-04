/**
 * The only place icons are imported from. Apps import icons from '@artha/design-system', never from 'lucide-react'
 * directly (ESLint enforces this). Add an icon here when a screen needs it: one curated list keeps the bundle small
 * and the visual language consistent (Lucide: 24px grid, 2px stroke, rounded caps).
 *
 * Usage rules: decorative icons get aria-hidden (Lucide sets it when no aria-label is passed); icon-only buttons need an
 * aria-label on the button; size with `className="size-4"` (inside Button this is automatic); colour with text-* tokens.
 */
export type { LucideIcon, LucideProps } from 'lucide-react'
export {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BellRing,
  BookOpen,
  CalendarRange,
  Check,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  Clock,
  Eye,
  EyeOff,
  FileClock,
  Flame,
  Info,
  KeyRound,
  Layers,
  ListChecks,
  LoaderCircle,
  Lock,
  LogOut,
  Mail,
  MailCheck,
  Menu,
  Moon,
  NotebookPen,
  Palette,
  RefreshCw,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  Sun,
  SunMoon,
  Timer,
  UserRound,
  X,
} from 'lucide-react'
