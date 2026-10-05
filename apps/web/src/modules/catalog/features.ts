import type { Feature } from './types'

/**
 * PROVISIONAL feature set. Replace/extend once the product feature screenshots are reviewed.
 * Adding an entry here automatically creates its /features/<slug> page, sitemap entry and landing card.
 */
export const features: Feature[] = [
  {
    slug: 'study-planner',
    title: 'Smart Study Planner',
    tagline: 'A day-by-day plan built backwards from your exam date.',
    description:
      'Tell us your course, level, exam date and daily hours. ArthaCommerce splits your time across subjects and phases (learn, revise, mock) and re-plans when you fall behind.',
    icon: 'calendar',
    highlights: [
      'Plans backwards from your exam date',
      'Learn, revise and mock phases',
      'Auto re-plan when you miss a day',
    ],
    status: 'soon',
  },
  {
    slug: 'syllabus-tracker',
    title: 'Syllabus Tracker',
    tagline: 'Every chapter, tracked from first read to final revision.',
    description:
      'See your whole syllabus as a progress map. Mark chapters as read, practised and revised, and know exactly where you stand in each subject.',
    icon: 'list-checks',
    highlights: [
      'Chapter-wise progress for each paper',
      'Read, practise, revise states',
      'Readiness score per subject',
    ],
    status: 'soon',
  },
  {
    slug: 'mock-tests',
    title: 'Mock Tests and Practice',
    tagline: 'Timed practice that feels like the real exam.',
    description:
      'Attempt chapter tests, subject mocks and full-length papers under exam conditions, then review mistakes with clear explanations.',
    icon: 'timer',
    highlights: ['Chapter, subject and full-length tests', 'Timed exam mode', 'Mistake review and retry'],
    status: 'soon',
  },
  {
    slug: 'ai-doubt-solver',
    title: 'AI Doubt Solver',
    tagline: 'Stuck on a concept at 11 pm? Ask.',
    description:
      'Ask doubts in plain language and get step-by-step explanations tied to your syllabus, powered by Google Gemini.',
    icon: 'sparkles',
    highlights: ['Step-by-step explanations', 'Syllabus-aware answers', 'Save answers to your notes'],
    status: 'soon',
  },
  {
    slug: 'smart-notes',
    title: 'Smart Notes',
    tagline: 'Your notes, organised by chapter, searchable in a second.',
    description:
      'Capture notes, highlights and formulae against the exact chapter they belong to, and find them instantly when you revise.',
    icon: 'notebook-pen',
    highlights: ['Notes linked to chapters', 'Instant search', 'Formula and section shortcuts'],
    status: 'soon',
  },
  {
    slug: 'flashcards',
    title: 'Flashcards and Spaced Revision',
    tagline: 'Revise what you are about to forget.',
    description:
      'Turn sections, definitions and case laws into flashcards. Spaced repetition schedules each card right before you would forget it.',
    icon: 'layers',
    highlights: ['Spaced repetition scheduling', 'Cards from your notes', 'Daily revision queue'],
    status: 'soon',
  },
  {
    slug: 'past-papers',
    title: 'Past Papers and Question Banks',
    tagline: 'Learn from what the examiner has already asked.',
    description:
      'Practise with past exam questions, revision and mock papers, organised by subject and chapter so you can target weak areas.',
    icon: 'file-clock',
    highlights: ['Organised by chapter', 'Filter by attempt', 'Track what you have solved'],
    status: 'soon',
  },
  {
    slug: 'streaks-analytics',
    title: 'Streaks and Analytics',
    tagline: 'See your effort compound.',
    description:
      'Study streaks, time spent per subject and score trends make progress visible, so showing up every day feels rewarding.',
    icon: 'flame',
    highlights: ['Daily study streaks', 'Time per subject', 'Score trends over time'],
    status: 'soon',
  },
  {
    slug: 'amendment-updates',
    title: 'Amendment and Notification Updates',
    tagline: 'Never study outdated law.',
    description:
      'Get alerts on law amendments and institute announcements that affect your attempt, mapped to the chapters they change.',
    icon: 'bell-ring',
    highlights: ['Mapped to affected chapters', 'Attempt-wise applicability', 'Institute announcement alerts'],
    status: 'soon',
  },
  {
    slug: 'pomodoro-focus-timer',
    title: 'Pomodoro Focus Timer',
    tagline: 'Study in focused rounds, then rest, without losing your place.',
    description:
      'Classic, Deep and Light rhythms or your own, with timed breaks, a gentle chime and a countdown in your browser tab. The clock runs on our server, so a reload or a second device shows the same time, and every finished round counts toward your daily goal.',
    icon: 'timer',
    highlights: [
      'Classic, Deep, Light and custom rhythms',
      'Breaks, long breaks and +5 minute extensions',
      'Counts toward your daily goal and streak',
    ],
    status: 'soon',
  },
  {
    slug: 'time-tracker',
    title: 'Study Time Tracker',
    tagline: 'Know where your hours really go.',
    description:
      'A stopwatch, manual entries and optional automatic logging while you read a chapter, with daily goals, a calendar heat map, time per subject and a comparison of time spent against chapters covered. Fix any entry, undo mistakes and download your data whenever you like.',
    icon: 'flame',
    highlights: [
      'Stopwatch, manual and optional automatic logging',
      'Daily and weekly goals with streaks',
      'Time per subject compared with coverage',
    ],
    status: 'soon',
  },
]

export const getFeature = (slug: string) => features.find((f) => f.slug === slug)
