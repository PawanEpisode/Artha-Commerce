import type { ReactNode } from 'react'

import type { Level } from '~/modules/catalog'

import { LevelDetail } from '../components/LevelDetail'
import type { PublicCourse } from '../lib/load'
import { CoveragePrompt } from './CoveragePrompt'

interface Props {
  course: PublicCourse
  level: Level
  syllabus?: ReactNode
  subjectCount?: number
  meta?: ReactNode
  report?: ReactNode
}

export function LevelDetailContainer({ course, level, ...rest }: Props) {
  return (
    <LevelDetail
      course={course}
      level={level}
      {...rest}
      prompt={
        <CoveragePrompt
          surface="level"
          course={{ slug: course.slug, name: course.name }}
          level={{ slug: level.slug, name: level.name }}
        />
      }
    />
  )
}
