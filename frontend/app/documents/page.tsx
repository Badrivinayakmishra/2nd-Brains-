'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  FileText,
  Search,
  Filter,
  Trash2,
  CheckSquare,
  Square,
  Loader2,
  MoreVertical,
} from 'lucide-react';
import { useDocuments, useDocumentStats, useBulkDelete } from '@/lib/hooks';
import { useAuthStore } from '@/lib/store';
import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { cn, formatDate, truncate } from '@/lib/utils';

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
  processing: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  classified: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  indexed: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
  failed: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
};

export default function DocumentsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuthStore();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(1);

  const { data: docsData, isLoading } = useDocuments({
    status: statusFilter || undefined,
    page,
    per_page: 20,
  });

  const { data: stats } = useDocumentStats();
  const bulkDelete = useBulkDelete();

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

  const documents = docsData?.documents || [];
  const total = docsData?.total || 0;

  const toggleSelect = (id: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const selectAll = () => {
    if (selectedIds.size === documents.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(documents.map((d: any) => d.id)));
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    if (!confirm(`Delete ${selectedIds.size} documents?`)) return;

    await bulkDelete.mutateAsync(Array.from(selectedIds));
    setSelectedIds(new Set());
  };

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-900">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
            {[
              { label: 'Total', value: stats?.total || 0, color: 'text-slate-900' },
              { label: 'Pending', value: stats?.pending || 0, color: 'text-yellow-600' },
              { label: 'Processing', value: stats?.processing || 0, color: 'text-blue-600' },
              { label: 'Classified', value: stats?.classified || 0, color: 'text-green-600' },
              { label: 'Indexed', value: stats?.indexed || 0, color: 'text-purple-600' },
              { label: 'Failed', value: stats?.failed || 0, color: 'text-red-600' },
            ].map((stat) => (
              <div key={stat.label} className="card p-4">
                <p className="text-sm text-slate-500 dark:text-slate-400">{stat.label}</p>
                <p className={cn('text-2xl font-bold', stat.color, 'dark:text-white')}>
                  {stat.value}
                </p>
              </div>
            ))}
          </div>

          {/* Toolbar */}
          <div className="flex items-center gap-4 mb-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search documents..."
                className="input pl-10 w-full max-w-md"
              />
            </div>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="input w-40"
            >
              <option value="">All Status</option>
              <option value="pending">Pending</option>
              <option value="processing">Processing</option>
              <option value="classified">Classified</option>
              <option value="indexed">Indexed</option>
              <option value="failed">Failed</option>
            </select>

            {selectedIds.size > 0 && (
              <button
                onClick={handleBulkDelete}
                disabled={bulkDelete.isPending}
                className="btn-danger flex items-center gap-2"
              >
                {bulkDelete.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4" />
                )}
                Delete ({selectedIds.size})
              </button>
            )}
          </div>

          {/* Documents table */}
          <div className="card overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 dark:bg-slate-800/50">
                <tr>
                  <th className="px-4 py-3 text-left">
                    <button onClick={selectAll} className="p-1">
                      {selectedIds.size === documents.length && documents.length > 0 ? (
                        <CheckSquare className="h-4 w-4 text-primary-600" />
                      ) : (
                        <Square className="h-4 w-4 text-slate-400" />
                      )}
                    </button>
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-600 dark:text-slate-300">
                    Title
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-600 dark:text-slate-300">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-600 dark:text-slate-300">
                    Classification
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-600 dark:text-slate-300">
                    Created
                  </th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                {isLoading ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center">
                      <Loader2 className="h-6 w-6 animate-spin mx-auto text-primary-500" />
                    </td>
                  </tr>
                ) : documents.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                      No documents found
                    </td>
                  </tr>
                ) : (
                  documents.map((doc: any) => (
                    <tr key={doc.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                      <td className="px-4 py-3">
                        <button onClick={() => toggleSelect(doc.id)} className="p-1">
                          {selectedIds.has(doc.id) ? (
                            <CheckSquare className="h-4 w-4 text-primary-600" />
                          ) : (
                            <Square className="h-4 w-4 text-slate-400" />
                          )}
                        </button>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <FileText className="h-5 w-5 text-slate-400" />
                          <span className="text-sm font-medium text-slate-900 dark:text-white">
                            {truncate(doc.title, 50)}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            'inline-flex px-2 py-1 text-xs font-medium rounded-full',
                            statusColors[doc.status] || statusColors.pending
                          )}
                        >
                          {doc.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">
                        {doc.classification || '-'}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">
                        {formatDate(doc.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <button className="btn-ghost p-1">
                          <MoreVertical className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>

            {/* Pagination */}
            {total > 20 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200 dark:border-slate-700">
                <p className="text-sm text-slate-600 dark:text-slate-400">
                  Showing {(page - 1) * 20 + 1} - {Math.min(page * 20, total)} of {total}
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="btn-secondary"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage((p) => p + 1)}
                    disabled={page * 20 >= total}
                    className="btn-secondary"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
