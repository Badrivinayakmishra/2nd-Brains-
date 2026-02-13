'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Brain,
  MessageSquare,
  FileText,
  Lightbulb,
  Settings,
  Plug,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useUIStore } from '@/lib/store';
import { cn } from '@/lib/utils';

const navigation = [
  { name: 'Chat', href: '/', icon: MessageSquare },
  { name: 'Documents', href: '/documents', icon: FileText },
  { name: 'Knowledge Gaps', href: '/knowledge-gaps', icon: Lightbulb },
  { name: 'Integrations', href: '/integrations', icon: Plug },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen, toggleSidebar } = useUIStore();

  return (
    <aside
      className={cn(
        'flex flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 transition-all duration-300',
        sidebarOpen ? 'w-64' : 'w-16'
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center justify-between border-b border-slate-200 dark:border-slate-800 px-4">
        <Link href="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-100 dark:bg-primary-900/30">
            <Brain className="h-5 w-5 text-primary-600 dark:text-primary-400" />
          </div>
          {sidebarOpen && (
            <span className="font-semibold text-slate-900 dark:text-white">
              2nd Brain
            </span>
          )}
        </Link>
        <button
          onClick={toggleSidebar}
          className="btn-ghost p-1.5 rounded-lg"
          aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          {sidebarOpen ? (
            <ChevronLeft className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-2">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;

          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/20 dark:text-primary-400'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white',
                !sidebarOpen && 'justify-center'
              )}
              title={!sidebarOpen ? item.name : undefined}
            >
              <Icon className="h-5 w-5 flex-shrink-0" />
              {sidebarOpen && <span>{item.name}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Version */}
      {sidebarOpen && (
        <div className="border-t border-slate-200 dark:border-slate-800 p-4">
          <p className="text-xs text-slate-500 dark:text-slate-500">
            2nd Brain v2.0.0
          </p>
        </div>
      )}
    </aside>
  );
}
