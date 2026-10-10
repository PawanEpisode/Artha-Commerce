import { type CourseSlug, getFeature } from '~/modules/catalog'

export const insightBand = {
  eyebrow: 'Why this exists',
  title: 'The syllabus is public. Your hours, coverage and notes are not.',
  body: 'Coaching PDFs, a timer on your phone, a spreadsheet of hours and a pile of flagged chapters. ArthaCommerce is the workspace that connects them, for every CA, CS and CMA attempt.',
}

export const courseStories: Record<
  CourseSlug,
  {
    outcome: string
    insight: string
  }
> = {
  ca: {
    outcome: 'One map from Foundation through Final and SPOM, chapter by chapter.',
    insight:
      'ICAI papers are public. Whether you have read, practised and revised each one is not — unless you track it.',
  },
  cs: {
    outcome: 'Company law, securities and governance without losing the amendment that changes the paper.',
    insight: 'CS rewards the student who revises the current law, not last attempt’s notes.',
  },
  cma: {
    outcome: 'Costing, strategy and finance with hours set against coverage, not a vague “I studied today”.',
    insight: 'CMA papers are won in practice sets. See which chapters got time, and which only got a highlight.',
  },
}

export const howItWorksBeats = [
  {
    id: 'goal',
    n: '01',
    rail: 'Your goal',
    title: 'Tell us the attempt',
    body: 'Course, level and exam date. It takes under a minute, and every tool afterwards — coverage, focus, hours — uses that same goal.',
    points: [
      'CA, CS or CMA, Foundation through Final',
      'An exam month, not a vague “someday”',
      'Change it later in settings if the attempt slips',
    ],
  },
  {
    id: 'today',
    n: '02',
    rail: 'Today',
    title: 'Follow a list, not a timetable poster',
    body: 'Each day should answer one question: what do I learn, revise and practise before I stop? The rest of the syllabus can wait.',
    points: [
      'A short list tied to chapters, not a 14-hour fantasy',
      'Focus rounds and logged hours count toward the same day',
      'Miss a day — pick up the chapter, not the guilt',
    ],
  },
  {
    id: 'readiness',
    n: '03',
    rail: 'Readiness',
    title: 'Watch readiness grow for real',
    body: 'Readiness is chapters finished and mocks attempted, not hours you meant to sit. The ring moves when the work does.',
    points: [
      'Read, practise, revise — each state is honest',
      'Time per paper compared with coverage, so weak chapters show up',
      'The same numbers follow you from the timer to the syllabus map',
    ],
  },
] as const

export interface FeatureBeat {
  slug: string
  rail: string
  headline: string
  insight: string
  points: readonly string[]
  cta: string
}

/** Live tools first so the first frames are real product UI. */
export const featureBeats: readonly FeatureBeat[] = [
  {
    slug: 'syllabus-tracker',
    rail: 'Syllabus',
    headline: 'Readiness is chapters finished, not hours logged.',
    insight:
      'A commerce attempt is a map: papers, chapters, first read, practice, revision. If that map lives in your head, you will over-study the chapter you like and skip the one that carries marks.',
    points: [
      'Mark read, practised and revised against the official structure',
      'See a readiness score per paper, not a single fake percentage',
      'Open any chapter from CA, CS or CMA without leaving the workspace',
    ],
    cta: 'See the syllabus map',
  },
  {
    slug: 'pomodoro-focus-timer',
    rail: 'Focus',
    headline: 'Sit for a round without losing the chapter.',
    insight:
      'The useful unit of exam prep is not “today”. It is 25 or 50 minutes on one topic, then a break you actually take. The clock has to survive a reload, a second device and the tab you forgot.',
    points: [
      'Classic, Deep and Light rhythms, or your own',
      'The round runs on our server, so a refresh does not wipe it',
      'Finished rounds count toward the same daily goal as the stopwatch',
    ],
    cta: 'How the timer works',
  },
  {
    slug: 'time-tracker',
    rail: 'Hours',
    headline: 'Know where the week actually went.',
    insight:
      'Students remember the evening they sat late. They forget the three days Advanced Accounting got nothing. Hours only help when they sit next to coverage.',
    points: [
      'Stopwatch, manual entries, optional auto-capture while you read',
      'Daily and weekly goals, with a calendar of hours',
      'Time per subject compared with chapters covered',
    ],
    cta: 'See the time tracker',
  },
  {
    slug: 'streaks-analytics',
    rail: 'Streaks',
    headline: 'A streak is only as honest as the hours behind it.',
    insight:
      'A flame on the home screen is motivating when it matches real sittings. The same numbers update when you finish a focus round or stop the stopwatch — not when you open the app.',
    points: [
      'Daily study streaks from actual logged time',
      'A calendar of hours, not a checkbox you can game',
      'Paper-wise totals so a 30-day streak still shows neglected law',
    ],
    cta: 'See streaks and hours',
  },
  {
    slug: 'smart-notes',
    rail: 'Notes',
    headline: 'A note that is not filed against the chapter vanishes at revision.',
    insight:
      'WhatsApp dumps, iPad galleries and three Google Docs do not survive the week before the exam. Notes here live under the chapter they belong to, search in a second, and keep working offline.',
    points: [
      'Headings, tables and formulas, saved as you type',
      'Each note sits on a syllabus chapter, not a nameless folder',
      'PDF library and a reader with marks, when you need the institute file',
    ],
    cta: 'See smart notes',
  },
  {
    slug: 'revision',
    rail: 'Revision',
    headline: 'Revise what you are about to forget, not what you already know.',
    insight:
      'Case laws, sections and formulas decay on a schedule. Revision puts each card in front of you just before it would have gone, which is the opposite of scrolling your highlights the night before.',
    points: [
      'Ready-made cards for sections, definitions and case laws, plus your own',
      'A daily queue, not a 400-card pile',
      'Scheduling that waits when you are sure, and returns when you are not',
    ],
    cta: 'See revision',
  },
  {
    slug: 'study-planner',
    rail: 'Planner',
    headline: 'Plan backwards from the exam date, not forwards from guilt.',
    insight:
      'A PDF timetable dies in week three. A useful plan starts from the sitting, splits learn / revise / mock, and re-plans when you miss a day — without pretending you will do 14 hours tomorrow.',
    points: [
      'Built from your course, level, exam date and daily hours',
      'Phases for first read, revision and mocks',
      'Re-plan when a week slips, instead of colouring the same grid again',
    ],
    cta: 'How the planner will work',
  },
  {
    slug: 'mock-tests',
    rail: 'Mocks',
    headline: 'Timed practice that feels like the hall, then a review that does not.',
    insight:
      'Writing a full paper at the dining table is useful only if you sit the clock, then spend longer on the mistakes than on the score. Chapter tests first; full papers when the coverage says you are ready.',
    points: [
      'Chapter, subject and full-length papers',
      'Exam-mode timing, then mistake review',
      'Retry the questions you actually missed',
    ],
    cta: 'How mocks will work',
  },
  {
    slug: 'ai-doubt-solver',
    rail: 'Doubts',
    headline: 'Stuck at 11 pm? Ask against the syllabus, not the open web.',
    insight:
      'A generic chatbot will invent a section. A doubt solver tied to your paper can walk the concept step by step — and you still cross-check it with the module, because AI can be wrong.',
    points: [
      'Plain-language questions, step-by-step answers',
      'Tied to the chapter you are on',
      'Save a useful answer into your notes',
    ],
    cta: 'How doubts will work',
  },
  {
    slug: 'past-papers',
    rail: 'Past papers',
    headline: 'The examiner has already told you what they ask.',
    insight:
      'RTP, MTP and past attempts are not a separate hobby. They belong next to the chapter, so you can see which topics keep returning and which illustrations you have never written.',
    points: ['Organised by subject and chapter', 'Filter by attempt', 'Track what you have already solved'],
    cta: 'How past papers will work',
  },
  {
    slug: 'amendment-updates',
    rail: 'Amendments',
    headline: 'Never study last attempt’s law by accident.',
    insight:
      'A notification on Instagram is not a study plan. Amendments matter when they are mapped to the chapter they change and to the sitting you are writing — applicable, or not, in one glance.',
    points: [
      'Institute announcements tied to chapters',
      'Attempt-wise applicability',
      'A reason to reopen the note, not another unread alert',
    ],
    cta: 'How amendments will work',
  },
]

export const walkthroughSlugs = featureBeats.map((beat) => beat.slug)

export function beatForSlug(slug: string) {
  return featureBeats.find((beat) => beat.slug === slug)
}

export function featureForBeat(beat: FeatureBeat) {
  const feature = getFeature(beat.slug)
  if (!feature) throw new Error(`Landing beat "${beat.slug}" is missing from the catalog`)
  return feature
}

export function paperCountForLevels(levels: ReadonlyArray<{ subjects: readonly string[] }>) {
  return levels.reduce((sum, level) => sum + level.subjects.length, 0)
}
