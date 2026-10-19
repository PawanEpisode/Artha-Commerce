import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '~/modules/auth'
import { personalizationKeys } from '~/modules/personalization'

import {
  fetchArticleship,
  fetchProgressionStatus,
  fetchTransitionHistory,
  fetchVaultEnrollments,
  postRollbackTransition,
  postTransition,
  updateArticleship,
} from '../lib/api'
import type { ArticleshipProfileData, TransitionPayload } from '../types'

export const progressionKeys = {
  root: ['progression'] as const,
  status: (userId: string | null) => ['progression', 'status', userId] as const,
  articleship: (userId: string | null) => ['progression', 'articleship', userId] as const,
  vault: (userId: string | null) => ['progression', 'vault', userId] as const,
  history: (userId: string | null) => ['progression', 'history', userId] as const,
}

export function useProgressionStatus() {
  const { user } = useAuth()
  return useQuery({
    queryKey: progressionKeys.status(user?.id ?? null),
    queryFn: fetchProgressionStatus,
    enabled: Boolean(user),
    staleTime: 30_000,
  })
}

export function useArticleship() {
  const { user } = useAuth()
  return useQuery({
    queryKey: progressionKeys.articleship(user?.id ?? null),
    queryFn: fetchArticleship,
    enabled: Boolean(user),
    staleTime: 30_000,
  })
}

export function useVaultEnrollments() {
  const { user } = useAuth()
  return useQuery({
    queryKey: progressionKeys.vault(user?.id ?? null),
    queryFn: fetchVaultEnrollments,
    enabled: Boolean(user),
    staleTime: 60_000,
  })
}

export function useTransitionHistory() {
  const { user } = useAuth()
  return useQuery({
    queryKey: progressionKeys.history(user?.id ?? null),
    queryFn: fetchTransitionHistory,
    enabled: Boolean(user),
    staleTime: 30_000,
  })
}

export function useTransitionMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: TransitionPayload) => postTransition(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: progressionKeys.root })
      void queryClient.invalidateQueries({ queryKey: personalizationKeys.bootstrap })
    },
  })
}

export function useRollbackMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (transitionId: string) => postRollbackTransition(transitionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: progressionKeys.root })
      void queryClient.invalidateQueries({ queryKey: personalizationKeys.bootstrap })
    },
  })
}

export function useArticleshipMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Partial<ArticleshipProfileData>) => updateArticleship(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: progressionKeys.articleship(null) })
      void queryClient.invalidateQueries({ queryKey: progressionKeys.status(null) })
      void queryClient.invalidateQueries({ queryKey: personalizationKeys.bootstrap })
    },
  })
}
