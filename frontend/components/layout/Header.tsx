'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { LogOut, User, Moon, Sun, Monitor } from 'lucide-react';
import { useAuthStore, useUIStore } from '@/lib/store';
import { useLogout } from '@/lib/hooks';

export function Header() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { theme, setTheme } = useUIStore();
  const logout = useLogout();
  const [showUserMenu, setShowUserMenu] = useState(false);

  const handleLogout = async () => {
    await logout.mutateAsync();
    router.push('/login');
  };

  const themeIcons = {
    light: Sun,
    dark: Moon,
    system: Monitor,
  };
  const ThemeIcon = themeIcons[theme];

  const cycleTheme = () => {
    const themes: ('light' | 'dark' | 'system')[] = ['light', 'dark', 'system'];
    const currentIndex = themes.indexOf(theme);
    const nextIndex = (currentIndex + 1) % themes.length;
    setTheme(themes[nextIndex]);
  };

  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6 dark:border-slate-800 dark:bg-slate-900">
      <div>
        {/* Breadcrumb or page title can go here */}
      </div>

      <div className="flex items-center gap-2">
        {/* Theme toggle */}
        <button
          onClick={cycleTheme}
          className="btn-ghost p-2 rounded-lg"
          title={`Theme: ${theme}`}
        >
          <ThemeIcon className="h-5 w-5" />
        </button>

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 btn-ghost px-3 py-2 rounded-lg"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-100 dark:bg-primary-900/30">
              <User className="h-4 w-4 text-primary-600 dark:text-primary-400" />
            </div>
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              {user?.full_name || user?.email?.split('@')[0] || 'User'}
            </span>
          </button>

          {showUserMenu && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setShowUserMenu(false)}
              />
              <div className="absolute right-0 top-full z-20 mt-2 w-48 rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-800">
                <div className="px-4 py-2 border-b border-slate-200 dark:border-slate-700">
                  <p className="text-sm font-medium text-slate-900 dark:text-white">
                    {user?.full_name || 'User'}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                    {user?.email}
                  </p>
                </div>
                <button
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20"
                >
                  <LogOut className="h-4 w-4" />
                  Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
