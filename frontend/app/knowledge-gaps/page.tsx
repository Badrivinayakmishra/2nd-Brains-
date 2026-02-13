'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Lightbulb,
  MessageSquare,
  X,
  Check,
  Loader2,
  Filter,
} from 'lucide-react';
import { useKnowledgeGaps, useKnowledgeGapStats, useAnswerGap } from '@/lib/hooks';
import { knowledgeGapApi } from '@/lib/api';
import { useAuthStore } from '@/lib/store';
import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { cn, formatRelativeTime } from '@/lib/utils';

const priorityColors: Record<number, string> = {
  5: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  4: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
  3: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
  2: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  1: 'bg-slate-100 text-slate-800 dark:bg-slate-700 dark:text-slate-300',
};

export default function KnowledgeGapsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuthStore();
  const [statusFilter, setStatusFilter] = useState<string>('open');
  const [selectedGap, setSelectedGap] = useState<any>(null);
  const [answer, setAnswer] = useState('');

  const { data: gapsData, isLoading, refetch } = useKnowledgeGaps({
    status: statusFilter || undefined,
  });

  const { data: stats } = useKnowledgeGapStats();
  const answerGap = useAnswerGap();

  if (authLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
      </div>
    );
  }

  if (!isAuthenticated) {
    router.push('/login');
    return null;
  }

  const gaps = gapsData?.gaps || [];

  const handleAnswer = async () => {
    if (!selectedGap || !answer.trim()) return;

    await answerGap.mutateAsync({ id: selectedGap.id, answer: answer.trim() });
    setSelectedGap(null);
    setAnswer('');
  };

  const handleDismiss = async (gapId: string) => {
    await knowledgeGapApi.dismiss(gapId);
    refetch();
  };

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-900">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
              Knowledge Gaps
            </h1>
            <p className="text-slate-600 dark:text-slate-400 mb-6">
              Questions identified from your documents that need answers.
            </p>

            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {[
                { label: 'Total', value: stats?.total || 0 },
                { label: 'Open', value: stats?.open || 0 },
                { label: 'Answered', value: stats?.answered || 0 },
                { label: 'High Priority', value: stats?.high_priority || 0 },
              ].map((stat) => (
                <div key={stat.label} className="card p-4">
                  <p className="text-sm text-slate-500 dark:text-slate-400">{stat.label}</p>
                  <p className="text-2xl font-bold text-slate-900 dark:text-white">
                    {stat.value}
                  </p>
                </div>
              ))}
            </div>

            {/* Filter */}
            <div className="flex items-center gap-4 mb-4">
              <Filter className="h-4 w-4 text-slate-400" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="input w-40"
              >
                <option value="">All</option>
                <option value="open">Open</option>
                <option value="answered">Answered</option>
                <option value="dismissed">Dismissed</option>
              </select>
            </div>

            {/* Gaps list */}
            <div className="space-y-4">
              {isLoading ? (
                <div className="card p-8 text-center">
                  <Loader2 className="h-6 w-6 animate-spin mx-auto text-primary-500" />
                </div>
              ) : gaps.length === 0 ? (
                <div className="card p-8 text-center">
                  <Lightbulb className="h-12 w-12 mx-auto text-slate-300 dark:text-slate-600 mb-4" />
                  <p className="text-slate-500 dark:text-slate-400">
                    No knowledge gaps found
                  </p>
                </div>
              ) : (
                gaps.map((gap: any) => (
                  <div
                    key={gap.id}
                    className={cn(
                      'card',
                      selectedGap?.id === gap.id && 'ring-2 ring-primary-500'
                    )}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span
                            className={cn(
                              'inline-flex px-2 py-0.5 text-xs font-medium rounded-full',
                              priorityColors[gap.priority] || priorityColors[1]
                            )}
                          >
                            P{gap.priority}
                          </span>
                          {gap.category && (
                            <span className="text-xs text-slate-500 dark:text-slate-400">
                              {gap.category}
                            </span>
                          )}
                          <span className="text-xs text-slate-400">
                            {formatRelativeTime(gap.created_at)}
                          </span>
                        </div>
                        <p className="text-slate-900 dark:text-white font-medium">
                          {gap.question}
                        </p>
                        {gap.answer && (
                          <div className="mt-3 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                            <p className="text-sm text-green-800 dark:text-green-300">
                              {gap.answer}
                            </p>
                          </div>
                        )}
                      </div>

                      {gap.status === 'open' && (
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setSelectedGap(gap)}
                            className="btn-secondary flex items-center gap-1 text-sm px-3 py-1.5"
                          >
                            <MessageSquare className="h-4 w-4" />
                            Answer
                          </button>
                          <button
                            onClick={() => handleDismiss(gap.id)}
                            className="btn-ghost p-1.5 text-slate-400 hover:text-slate-600"
                            title="Dismiss"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Answer form */}
                    {selectedGap?.id === gap.id && (
                      <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700">
                        <textarea
                          value={answer}
                          onChange={(e) => setAnswer(e.target.value)}
                          placeholder="Type your answer..."
                          className="input w-full h-24 resize-none mb-3"
                        />
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => {
                              setSelectedGap(null);
                              setAnswer('');
                            }}
                            className="btn-secondary"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={handleAnswer}
                            disabled={!answer.trim() || answerGap.isPending}
                            className="btn-primary flex items-center gap-2"
                          >
                            {answerGap.isPending ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Check className="h-4 w-4" />
                            )}
                            Submit Answer
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
