'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Plus, Loader2, Bot, User, Sparkles } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useChatStore } from '@/lib/store';
import { useChatSessions, useChatMessages, useCreateChatSession } from '@/lib/hooks';
import { chatApi } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';

export function Chat() {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const {
    currentSessionId,
    messages,
    isStreaming,
    setCurrentSession,
    setMessages,
    addMessage,
    updateLastMessage,
    setStreaming,
  } = useChatStore();

  const { data: sessions } = useChatSessions();
  const { data: sessionMessages } = useChatMessages(currentSessionId);
  const createSession = useCreateChatSession();

  // Load messages when session changes
  useEffect(() => {
    if (sessionMessages) {
      setMessages(
        sessionMessages.map((m: any) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          sources: m.sources,
          createdAt: m.created_at,
        }))
      );
    }
  }, [sessionMessages, setMessages]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-focus input
  useEffect(() => {
    inputRef.current?.focus();
  }, [currentSessionId]);

  const handleNewChat = async () => {
    const session = await createSession.mutateAsync();
    setCurrentSession(session.id);
    setMessages([]);
  };

  const handleSend = useCallback(async () => {
    if (!input.trim() || isStreaming) return;

    const userMessage = input.trim();
    setInput('');

    // Create session if none exists
    let sessionId = currentSessionId;
    if (!sessionId) {
      const session = await createSession.mutateAsync();
      sessionId = session.id;
      setCurrentSession(sessionId);
    }

    // Add user message
    addMessage({
      id: Date.now().toString(),
      role: 'user',
      content: userMessage,
      createdAt: new Date().toISOString(),
    });

    // Add placeholder assistant message
    addMessage({
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      createdAt: new Date().toISOString(),
    });

    setStreaming(true);

    try {
      // Stream response
      const response = await chatApi.streamMessage(sessionId, userMessage);
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') continue;
              fullContent += data;
              updateLastMessage(fullContent);
            }
          }
        }
      }
    } catch (error) {
      console.error('Chat error:', error);
      updateLastMessage('Sorry, there was an error processing your message. Please try again.');
    } finally {
      setStreaming(false);
    }
  }, [
    input,
    isStreaming,
    currentSessionId,
    createSession,
    setCurrentSession,
    addMessage,
    updateLastMessage,
    setStreaming,
  ]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-full">
      {/* Chat sessions sidebar */}
      <div className="w-64 border-r border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 flex flex-col">
        <div className="p-4">
          <button
            onClick={handleNewChat}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            <Plus className="h-4 w-4" />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-thin px-2 pb-4">
          {sessions?.map((session: any) => (
            <button
              key={session.id}
              onClick={() => setCurrentSession(session.id)}
              className={cn(
                'w-full text-left px-3 py-2 rounded-lg mb-1 transition-colors',
                currentSessionId === session.id
                  ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300'
                  : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300'
              )}
            >
              <p className="text-sm font-medium truncate">
                {session.title || 'New Chat'}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {formatRelativeTime(session.updated_at)}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary-100 dark:bg-primary-900/30 mb-4">
                <Sparkles className="h-8 w-8 text-primary-600 dark:text-primary-400" />
              </div>
              <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
                Welcome to 2nd Brain
              </h2>
              <p className="text-slate-600 dark:text-slate-400 max-w-md">
                Ask questions about your documents and knowledge base.
                I'll help you find information and make connections.
              </p>
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  'flex gap-3',
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                )}
              >
                {message.role === 'assistant' && (
                  <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-primary-100 dark:bg-primary-900/30">
                    <Bot className="h-5 w-5 text-primary-600 dark:text-primary-400" />
                  </div>
                )}

                <div
                  className={cn(
                    'max-w-[70%] rounded-2xl px-4 py-2',
                    message.role === 'user'
                      ? 'bg-primary-600 text-white'
                      : 'bg-slate-100 dark:bg-slate-800'
                  )}
                >
                  {message.role === 'assistant' ? (
                    <div className="prose-chat">
                      <ReactMarkdown>{message.content || '...'}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-sm">{message.content}</p>
                  )}
                </div>

                {message.role === 'user' && (
                  <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-slate-200 dark:bg-slate-700">
                    <User className="h-5 w-5 text-slate-600 dark:text-slate-400" />
                  </div>
                )}
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t border-slate-200 dark:border-slate-800 p-4">
          <div className="flex items-end gap-3">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a question about your knowledge base..."
                className="input resize-none min-h-[44px] max-h-32 pr-12"
                rows={1}
                disabled={isStreaming}
              />
            </div>
            <button
              onClick={handleSend}
              disabled={!input.trim() || isStreaming}
              className="btn-primary px-4 py-2.5"
            >
              {isStreaming ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Send className="h-5 w-5" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
