/**
 * API client with proper error handling and token management.
 * Fixes the session management issues from the original.
 */
import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// Token storage keys
const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Token management
export const tokenManager = {
  getAccessToken: (): string | null => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  },

  getRefreshToken: (): string | null => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },

  setTokens: (accessToken: string, refreshToken: string): void => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  },

  clearTokens: (): void => {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};

// Request interceptor - add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = tokenManager.getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle token refresh
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

const subscribeTokenRefresh = (callback: (token: string) => void) => {
  refreshSubscribers.push(callback);
};

const onTokenRefreshed = (token: string) => {
  refreshSubscribers.forEach((callback) => callback(token));
  refreshSubscribers = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // If 401 and not already retrying
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Wait for token refresh
        return new Promise((resolve) => {
          subscribeTokenRefresh((token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            resolve(api(originalRequest));
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = tokenManager.getRefreshToken();
      if (!refreshToken) {
        tokenManager.clearTokens();
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        const response = await axios.post(`${API_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const { access_token, refresh_token } = response.data;
        tokenManager.setTokens(access_token, refresh_token);
        onTokenRefreshed(access_token);
        isRefreshing = false;

        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        tokenManager.clearTokens();
        window.location.href = '/login';
        isRefreshing = false;
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// API methods
export const authApi = {
  login: async (email: string, password: string) => {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return response.data;
  },

  signup: async (email: string, password: string, fullName?: string) => {
    const response = await api.post('/auth/signup', {
      email,
      password,
      full_name: fullName,
    });
    return response.data;
  },

  logout: async () => {
    const refreshToken = tokenManager.getRefreshToken();
    if (refreshToken) {
      await api.post('/auth/logout', { refresh_token: refreshToken });
    }
    tokenManager.clearTokens();
  },

  me: async () => {
    const response = await api.get('/auth/me');
    return response.data;
  },
};

export const documentApi = {
  list: async (params?: {
    status?: string;
    project_id?: string;
    page?: number;
    per_page?: number;
  }) => {
    const response = await api.get('/documents', { params });
    return response.data;
  },

  get: async (id: string) => {
    const response = await api.get(`/documents/${id}`);
    return response.data;
  },

  create: async (data: { title: string; content?: string; metadata?: object }) => {
    const response = await api.post('/documents', data);
    return response.data;
  },

  delete: async (id: string) => {
    await api.delete(`/documents/${id}`);
  },

  bulkClassify: async (documentIds: string[], classification: string) => {
    const response = await api.post('/documents/bulk/classify', {
      document_ids: documentIds,
      classification,
    });
    return response.data;
  },

  bulkDelete: async (documentIds: string[]) => {
    const response = await api.post('/documents/bulk/delete', {
      document_ids: documentIds,
    });
    return response.data;
  },

  stats: async () => {
    const response = await api.get('/documents/stats');
    return response.data;
  },
};

export const chatApi = {
  listSessions: async () => {
    const response = await api.get('/chat/sessions');
    return response.data;
  },

  createSession: async (title?: string) => {
    const response = await api.post('/chat/sessions', { title });
    return response.data;
  },

  getSession: async (id: string) => {
    const response = await api.get(`/chat/sessions/${id}`);
    return response.data;
  },

  deleteSession: async (id: string) => {
    await api.delete(`/chat/sessions/${id}`);
  },

  getMessages: async (sessionId: string) => {
    const response = await api.get(`/chat/sessions/${sessionId}/messages`);
    return response.data;
  },

  sendMessage: async (sessionId: string, message: string) => {
    const response = await api.post(`/chat/sessions/${sessionId}/chat`, {
      message,
    });
    return response.data;
  },

  // Streaming endpoint
  streamMessage: (sessionId: string, message: string) => {
    const token = tokenManager.getAccessToken();
    return fetch(`${API_URL}/chat/sessions/${sessionId}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ message }),
    });
  },
};

export const knowledgeGapApi = {
  list: async (params?: {
    status?: string;
    category?: string;
    page?: number;
    per_page?: number;
  }) => {
    const response = await api.get('/knowledge-gaps', { params });
    return response.data;
  },

  get: async (id: string) => {
    const response = await api.get(`/knowledge-gaps/${id}`);
    return response.data;
  },

  create: async (data: { question: string; category?: string; priority?: number }) => {
    const response = await api.post('/knowledge-gaps', data);
    return response.data;
  },

  answer: async (id: string, answer: string) => {
    const response = await api.post(`/knowledge-gaps/${id}/answer`, { answer });
    return response.data;
  },

  dismiss: async (id: string) => {
    await api.post(`/knowledge-gaps/${id}/dismiss`);
  },

  stats: async () => {
    const response = await api.get('/knowledge-gaps/stats');
    return response.data;
  },

  categories: async () => {
    const response = await api.get('/knowledge-gaps/categories');
    return response.data;
  },
};

export const integrationApi = {
  listConnectors: async () => {
    const response = await api.get('/integrations/connectors');
    return response.data;
  },

  getConnector: async (id: string) => {
    const response = await api.get(`/integrations/connectors/${id}`);
    return response.data;
  },

  deleteConnector: async (id: string) => {
    await api.delete(`/integrations/connectors/${id}`);
  },

  startSync: async (connectorId: string) => {
    const response = await api.post(`/integrations/connectors/${connectorId}/sync`);
    return response.data;
  },

  getSyncProgress: async (connectorId: string) => {
    const response = await api.get(`/integrations/connectors/${connectorId}/progress`);
    return response.data;
  },

  getOAuthUrl: async (connectorType: string) => {
    const response = await api.get(`/integrations/${connectorType}/oauth/url`);
    return response.data;
  },

  completeOAuth: async (connectorType: string, code: string) => {
    const response = await api.post(`/integrations/${connectorType}/oauth/callback`, {
      code,
    });
    return response.data;
  },
};

export default api;
