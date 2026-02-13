/**
 * Global state management using Zustand.
 * Clean, type-safe state without the complexity of Redux.
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Types
interface User {
  id: string;
  email: string;
  full_name?: string;
  is_verified: boolean;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
}

interface UIState {
  sidebarOpen: boolean;
  theme: 'light' | 'dark' | 'system';
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
}

interface SyncProgress {
  connectorId: string;
  status: string;
  percent: number;
  currentStep?: string;
  totalItems: number;
  processedItems: number;
}

interface SyncState {
  activeSync: SyncProgress | null;
  setActiveSync: (sync: SyncProgress | null) => void;
  updateSyncProgress: (progress: Partial<SyncProgress>) => void;
}

// Auth store
export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  setUser: (user) =>
    set({
      user,
      isAuthenticated: !!user,
      isLoading: false,
    }),

  setLoading: (isLoading) => set({ isLoading }),

  logout: () =>
    set({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    }),
}));

// UI store with persistence
export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      theme: 'system',

      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: 'ui-preferences',
      partialize: (state) => ({ theme: state.theme }),
    }
  )
);

// Sync progress store
export const useSyncStore = create<SyncState>((set) => ({
  activeSync: null,

  setActiveSync: (activeSync) => set({ activeSync }),

  updateSyncProgress: (progress) =>
    set((state) => ({
      activeSync: state.activeSync
        ? { ...state.activeSync, ...progress }
        : null,
    })),
}));

// Chat store for managing chat state
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
  createdAt: string;
}

interface ChatState {
  currentSessionId: string | null;
  messages: ChatMessage[];
  isStreaming: boolean;
  setCurrentSession: (sessionId: string | null) => void;
  setMessages: (messages: ChatMessage[]) => void;
  addMessage: (message: ChatMessage) => void;
  updateLastMessage: (content: string) => void;
  setStreaming: (streaming: boolean) => void;
  clearChat: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  currentSessionId: null,
  messages: [],
  isStreaming: false,

  setCurrentSession: (currentSessionId) => set({ currentSessionId, messages: [] }),

  setMessages: (messages) => set({ messages }),

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  updateLastMessage: (content) =>
    set((state) => {
      const messages = [...state.messages];
      if (messages.length > 0) {
        messages[messages.length - 1] = {
          ...messages[messages.length - 1],
          content,
        };
      }
      return { messages };
    }),

  setStreaming: (isStreaming) => set({ isStreaming }),

  clearChat: () => set({ messages: [], currentSessionId: null }),
}));
