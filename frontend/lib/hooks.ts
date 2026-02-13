/**
 * Custom hooks for data fetching and state management.
 * Uses React Query for caching and background updates.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  authApi,
  documentApi,
  chatApi,
  knowledgeGapApi,
  integrationApi,
  tokenManager,
} from './api';
import { useAuthStore, useSyncStore } from './store';

// Query keys for cache management
export const queryKeys = {
  user: ['user'] as const,
  documents: (params?: object) => ['documents', params] as const,
  documentStats: ['documents', 'stats'] as const,
  chatSessions: ['chat', 'sessions'] as const,
  chatMessages: (sessionId: string) => ['chat', 'messages', sessionId] as const,
  knowledgeGaps: (params?: object) => ['knowledge-gaps', params] as const,
  knowledgeGapStats: ['knowledge-gaps', 'stats'] as const,
  connectors: ['connectors'] as const,
  syncProgress: (connectorId: string) => ['sync', 'progress', connectorId] as const,
};

// Auth hooks
export function useUser() {
  const { setUser, setLoading } = useAuthStore();

  return useQuery({
    queryKey: queryKeys.user,
    queryFn: async () => {
      const token = tokenManager.getAccessToken();
      if (!token) {
        setUser(null);
        return null;
      }
      try {
        const user = await authApi.me();
        setUser(user);
        return user;
      } catch {
        setUser(null);
        return null;
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: false,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  const { setUser } = useAuthStore();

  return useMutation({
    mutationFn: async ({ email, password }: { email: string; password: string }) => {
      const tokens = await authApi.login(email, password);
      tokenManager.setTokens(tokens.access_token, tokens.refresh_token);
      return tokens;
    },
    onSuccess: async () => {
      const user = await authApi.me();
      setUser(user);
      queryClient.setQueryData(queryKeys.user, user);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  const { logout } = useAuthStore();

  return useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      logout();
      queryClient.clear();
    },
  });
}

// Document hooks
export function useDocuments(params?: {
  status?: string;
  project_id?: string;
  page?: number;
  per_page?: number;
}) {
  return useQuery({
    queryKey: queryKeys.documents(params),
    queryFn: () => documentApi.list(params),
    staleTime: 30 * 1000, // 30 seconds
  });
}

export function useDocumentStats() {
  return useQuery({
    queryKey: queryKeys.documentStats,
    queryFn: documentApi.stats,
    staleTime: 60 * 1000, // 1 minute
  });
}

export function useBulkClassify() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ ids, classification }: { ids: string[]; classification: string }) =>
      documentApi.bulkClassify(ids, classification),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}

export function useBulkDelete() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (ids: string[]) => documentApi.bulkDelete(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}

// Chat hooks
export function useChatSessions() {
  return useQuery({
    queryKey: queryKeys.chatSessions,
    queryFn: chatApi.listSessions,
    staleTime: 30 * 1000,
  });
}

export function useChatMessages(sessionId: string | null) {
  return useQuery({
    queryKey: queryKeys.chatMessages(sessionId || ''),
    queryFn: () => (sessionId ? chatApi.getMessages(sessionId) : Promise.resolve([])),
    enabled: !!sessionId,
    staleTime: 0, // Always fresh for chat
  });
}

export function useCreateChatSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (title?: string) => chatApi.createSession(title),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.chatSessions });
    },
  });
}

// Knowledge gap hooks
export function useKnowledgeGaps(params?: {
  status?: string;
  category?: string;
  page?: number;
  per_page?: number;
}) {
  return useQuery({
    queryKey: queryKeys.knowledgeGaps(params),
    queryFn: () => knowledgeGapApi.list(params),
    staleTime: 60 * 1000,
  });
}

export function useKnowledgeGapStats() {
  return useQuery({
    queryKey: queryKeys.knowledgeGapStats,
    queryFn: knowledgeGapApi.stats,
    staleTime: 60 * 1000,
  });
}

export function useAnswerGap() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, answer }: { id: string; answer: string }) =>
      knowledgeGapApi.answer(id, answer),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-gaps'] });
    },
  });
}

// Integration hooks
export function useConnectors() {
  return useQuery({
    queryKey: queryKeys.connectors,
    queryFn: integrationApi.listConnectors,
    staleTime: 30 * 1000,
  });
}

export function useStartSync() {
  const { setActiveSync } = useSyncStore();

  return useMutation({
    mutationFn: (connectorId: string) => integrationApi.startSync(connectorId),
    onSuccess: (_, connectorId) => {
      setActiveSync({
        connectorId,
        status: 'syncing',
        percent: 0,
        totalItems: 0,
        processedItems: 0,
      });
    },
  });
}

/**
 * Optimized sync progress polling hook.
 * Fixes the XHR spam issue from the original by using:
 * - Exponential backoff (2s -> 10s)
 * - Forward-only progress updates (prevents jumping)
 * - Auto-stop when complete
 */
export function useSyncProgress(connectorId: string | null) {
  const { activeSync, updateSyncProgress, setActiveSync } = useSyncStore();
  const [pollInterval, setPollInterval] = useState(2000);
  const lastProgressRef = useRef(0);

  const query = useQuery({
    queryKey: queryKeys.syncProgress(connectorId || ''),
    queryFn: () => (connectorId ? integrationApi.getSyncProgress(connectorId) : null),
    enabled: !!connectorId && activeSync?.status === 'syncing',
    refetchInterval: pollInterval,
    staleTime: 0,
  });

  useEffect(() => {
    if (query.data) {
      const progress = query.data;

      // Only update if progress moved forward (prevents jumping)
      if (progress.processed_items >= lastProgressRef.current) {
        lastProgressRef.current = progress.processed_items;

        updateSyncProgress({
          status: progress.status,
          percent: progress.percent,
          currentStep: progress.current_step,
          totalItems: progress.total_items,
          processedItems: progress.processed_items,
        });
      }

      // Exponential backoff while syncing
      if (progress.status === 'syncing') {
        setPollInterval((prev) => Math.min(prev * 1.2, 10000));
      }

      // Stop polling when complete or failed
      if (progress.status === 'completed' || progress.status === 'failed') {
        setActiveSync({
          ...activeSync!,
          status: progress.status,
          percent: 100,
        });
        setPollInterval(0);
      }
    }
  }, [query.data]);

  // Reset interval when starting new sync
  useEffect(() => {
    if (activeSync?.status === 'syncing') {
      setPollInterval(2000);
      lastProgressRef.current = 0;
    }
  }, [activeSync?.connectorId]);

  return query;
}

// Debounce hook for search inputs
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}
