import type { Course, CourseSlug } from './types'

/**
 * Single source of truth for courses. Landing, course pages, planner preview and sitemap all read from here.
 * Subject lists are indicative; the real syllabus will be managed in the database (see docs/ARCHITECTURE.md).
 */
export const courses: Course[] = [
  {
    slug: 'ca',
    name: 'CA',
    fullName: 'Chartered Accountancy',
    body: 'ICAI',
    bodyFullName: 'The Institute of Chartered Accountants of India',
    tagline: 'From Foundation to Final, one workspace.',
    description:
      'Plan, practise and revise every paper of the CA Foundation, Intermediate and Final levels with chapter-wise tracking and mock tests.',
    levels: [
      {
        slug: 'foundation',
        name: 'Foundation',
        subjects: [
          'Principles and Practice of Accounting',
          'Business Laws',
          'Business Mathematics, Logical Reasoning and Statistics',
          'Business Economics and Business and Commercial Knowledge',
        ],
      },
      {
        slug: 'intermediate',
        name: 'Intermediate',
        subjects: [
          'Advanced Accounting',
          'Corporate and Other Laws',
          'Taxation',
          'Cost and Management Accounting',
          'Auditing and Ethics',
          'Financial Management and Strategic Management',
        ],
      },
      {
        slug: 'final',
        name: 'Final',
        subjects: [
          'Financial Reporting',
          'Advanced Financial Management',
          'Advanced Auditing, Assurance and Professional Ethics',
          'Direct and International Tax Laws',
          'Indirect Tax Laws',
          'Integrated Business Solutions',
        ],
      },
    ],
  },
  {
    slug: 'cs',
    name: 'CS',
    fullName: 'Company Secretaryship',
    body: 'ICSI',
    bodyFullName: 'The Institute of Company Secretaries of India',
    tagline: 'Master laws, governance and compliance.',
    description:
      'Stay on top of company law, securities law and governance papers with amendment-aware notes and structured revision.',
    levels: [
      {
        slug: 'foundation',
        name: 'Foundation',
        subjects: [
          'Business Environment and Law',
          'Business Management, Ethics and Entrepreneurship',
          'Business Economics',
          'Fundamentals of Accounting and Auditing',
        ],
      },
      {
        slug: 'executive',
        name: 'Executive',
        subjects: [
          'Jurisprudence, Interpretation and General Laws',
          'Company Law',
          'Setting up of Business Entities and Closure',
          'Tax Laws',
          'Corporate and Management Accountancy',
          'Securities Laws and Capital Markets',
          'Economic, Business and Commercial Laws',
        ],
      },
      {
        slug: 'professional',
        name: 'Professional',
        subjects: [
          'Governance, Risk Management, Compliances and Ethics',
          'Advanced Tax Laws',
          'Drafting, Pleadings and Appearances',
          'Compliance Management, Audit and Due Diligence',
          'Corporate Restructuring, Insolvency, Liquidation and Winding-up',
        ],
      },
    ],
  },
  {
    slug: 'cma',
    name: 'CMA',
    fullName: 'Cost and Management Accountancy',
    body: 'ICMAI',
    bodyFullName: 'The Institute of Cost Accountants of India',
    tagline: 'Costing, strategy and finance, simplified.',
    description:
      'Build mastery in costing, management accounting and strategic finance with practice sets and spaced revision.',
    levels: [
      {
        slug: 'foundation',
        name: 'Foundation',
        subjects: [
          'Fundamentals of Business Laws and Business Communication',
          'Fundamentals of Financial and Cost Accounting',
          'Fundamentals of Business Mathematics and Statistics',
          'Fundamentals of Business Economics and Management',
        ],
      },
      {
        slug: 'intermediate',
        name: 'Intermediate',
        subjects: [
          'Business Laws and Ethics',
          'Financial Accounting',
          'Direct and Indirect Taxation',
          'Cost Accounting',
          'Operations Management and Strategic Management',
          'Corporate Accounting and Auditing',
          'Financial Management and Business Data Analytics',
        ],
      },
      {
        slug: 'final',
        name: 'Final',
        subjects: [
          'Corporate and Economic Laws',
          'Strategic Financial Management',
          'Direct Tax Laws and International Taxation',
          'Strategic Cost Management',
          'Cost and Management Audit',
          'Corporate Financial Reporting',
          'Indirect Tax Laws and Practice',
          'Strategic Performance Management and Business Valuation',
        ],
      },
    ],
  },
]

export const getCourse = (slug: string) => courses.find((c) => c.slug === (slug as CourseSlug))

export const getLevel = (courseSlug: string, levelSlug: string) =>
  getCourse(courseSlug)?.levels.find((l) => l.slug === levelSlug)
