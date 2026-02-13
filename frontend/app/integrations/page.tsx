'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Plug,
  RefreshCw,
  Check,
  AlertCircle,
  Loader2,
  ExternalLink,
} from 'lucide-react';
import { useConnectors, useStartSync, useSyncProgress } from '@/lib/hooks';
import { useAuthStore, useSyncStore } from '@/lib/store';
import { integrationApi } from '@/lib/api';
import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { cn } from '@/lib/utils';

const connectorIcons: Record<string, string> = {
  google_drive: '/icons/google-drive.svg',
  gmail: '/icons/gmail.svg',
  slack: '/icons/slack.svg',
  notion: '/icons/notion.svg',
  github: '/icons/github.svg',
};

const availableConnectors = [
  {
    type: 'google_drive',
    name: 'Google Drive',
    description: 'Sync documents from your Google Drive',
  },
  {
    type: 'gmail',
    name: 'Gmail',
    description: 'Import emails and attachments',
  },
  {
    type: 'slack',
    name: 'Slack',
    description: 'Sync messages and files from Slack channels',
  },
  {
    type: 'notion',
    name: 'Notion',
    description: 'Import pages and databases from Notion',
  },
  {
    type: 'github',
    name: 'GitHub',
    description: 'Sync repositories, issues, and documentation',
  },
];

export default function IntegrationsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuthStore();
  const { activeSync } = useSyncStore();
  const [connecting, setConnecting] = useState<string | null>(null);

  const { data: connectors, isLoading } = useConnectors();
  const startSync = useStartSync();

  // Poll progress for active sync
  useSyncProgress(activeSync?.connectorId || null);

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

  const connectedConnectors = connectors || [];
  const connectedTypes = new Set(connectedConnectors.map((c: any) => c.connector_type));

  const handleConnect = async (connectorType: string) => {
    setConnecting(connectorType);
    try {
      const { url } = await integrationApi.getOAuthUrl(connectorType);
      window.location.href = url;
    } catch (error) {
      console.error('Failed to get OAuth URL:', error);
      setConnecting(null);
    }
  };

  const handleSync = async (connectorId: string) => {
    await startSync.mutateAsync(connectorId);
  };

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-900">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
              Integrations
            </h1>
            <p className="text-slate-600 dark:text-slate-400 mb-8">
              Connect your tools to sync knowledge into your second brain.
            </p>

            {/* Active Sync Progress */}
            {activeSync && activeSync.status === 'syncing' && (
              <div className="card mb-6 bg-primary-50 dark:bg-primary-900/20 border-primary-200 dark:border-primary-800">
                <div className="flex items-center gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-100 dark:bg-primary-900/30">
                    <RefreshCw className="h-5 w-5 text-primary-600 animate-spin" />
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-slate-900 dark:text-white">
                      Syncing in progress...
                    </p>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      {activeSync.currentStep || `${activeSync.processedItems} / ${activeSync.totalItems} items`}
                    </p>
                    <div className="mt-2 h-2 w-full bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary-500 transition-all duration-300"
                        style={{ width: `${activeSync.percent}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Connected Integrations */}
            {connectedConnectors.length > 0 && (
              <section className="mb-8">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
                  Connected
                </h2>
                <div className="grid gap-4">
                  {connectedConnectors.map((connector: any) => (
                    <div
                      key={connector.id}
                      className="card flex items-center justify-between"
                    >
                      <div className="flex items-center gap-4">
                        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800">
                          <Plug className="h-6 w-6 text-slate-600 dark:text-slate-400" />
                        </div>
                        <div>
                          <p className="font-medium text-slate-900 dark:text-white">
                            {connector.name}
                          </p>
                          <div className="flex items-center gap-2 text-sm">
                            {connector.sync_status === 'completed' ? (
                              <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
                                <Check className="h-4 w-4" />
                                Synced
                              </span>
                            ) : connector.sync_status === 'failed' ? (
                              <span className="flex items-center gap-1 text-red-600 dark:text-red-400">
                                <AlertCircle className="h-4 w-4" />
                                Failed
                              </span>
                            ) : (
                              <span className="text-slate-500">Ready to sync</span>
                            )}
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => handleSync(connector.id)}
                        disabled={
                          startSync.isPending ||
                          (activeSync?.connectorId === connector.id &&
                            activeSync?.status === 'syncing')
                        }
                        className="btn-secondary flex items-center gap-2"
                      >
                        {activeSync?.connectorId === connector.id &&
                        activeSync?.status === 'syncing' ? (
                          <>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Syncing...
                          </>
                        ) : (
                          <>
                            <RefreshCw className="h-4 w-4" />
                            Sync
                          </>
                        )}
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Available Integrations */}
            <section>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
                {connectedConnectors.length > 0 ? 'Add More' : 'Available Integrations'}
              </h2>
              <div className="grid gap-4">
                {availableConnectors
                  .filter((c) => !connectedTypes.has(c.type))
                  .map((connector) => (
                    <div
                      key={connector.type}
                      className="card flex items-center justify-between"
                    >
                      <div className="flex items-center gap-4">
                        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800">
                          <Plug className="h-6 w-6 text-slate-600 dark:text-slate-400" />
                        </div>
                        <div>
                          <p className="font-medium text-slate-900 dark:text-white">
                            {connector.name}
                          </p>
                          <p className="text-sm text-slate-500 dark:text-slate-400">
                            {connector.description}
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => handleConnect(connector.type)}
                        disabled={connecting === connector.type}
                        className="btn-primary flex items-center gap-2"
                      >
                        {connecting === connector.type ? (
                          <>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Connecting...
                          </>
                        ) : (
                          <>
                            <ExternalLink className="h-4 w-4" />
                            Connect
                          </>
                        )}
                      </button>
                    </div>
                  ))}
              </div>
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}
