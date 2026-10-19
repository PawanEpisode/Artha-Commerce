import { api } from '~/lib/api'

import type {
  ArticleshipProfileData,
  ProgressionStatus,
  RollbackResult,
  TransitionHistoryItem,
  TransitionPayload,
  TransitionResult,
  VaultEnrollment,
} from '../types'

const json = (body: unknown) => JSON.stringify(body)

export const fetchProgressionStatus = async (): Promise<ProgressionStatus> =>
  api<ProgressionStatus>('/progression/status/')

export const postTransition = async (payload: TransitionPayload): Promise<TransitionResult> =>
  api<TransitionResult>('/progression/transition/', {
    method: 'POST',
    body: json(payload),
  })

export const postRollbackTransition = async (transitionId: string): Promise<RollbackResult> =>
  api<RollbackResult>('/progression/transition/rollback/', {
    method: 'POST',
    body: json({ transition_id: transitionId }),
  })

export const fetchArticleship = async (): Promise<ArticleshipProfileData> =>
  api<ArticleshipProfileData>('/progression/articleship/')

export const updateArticleship = async (payload: Partial<ArticleshipProfileData>): Promise<ArticleshipProfileData> =>
  api<ArticleshipProfileData>('/progression/articleship/', {
    method: 'PUT',
    body: json(payload),
  })

export const fetchVaultEnrollments = async (): Promise<{ enrollments: VaultEnrollment[] }> =>
  api<{ enrollments: VaultEnrollment[] }>('/progression/vault/')

export const fetchTransitionHistory = async (): Promise<{ history: TransitionHistoryItem[] }> =>
  api<{ history: TransitionHistoryItem[] }>('/progression/history/')
