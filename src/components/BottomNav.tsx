import React from 'react';
import { LayoutDashboard, Radio, Layers, Rss, MoreHorizontal } from 'lucide-react';

export type NavTab = 'dashboard' | 'channels' | 'posts' | 'sources' | 'more' | 'users' | 'distribution' | 'alerts' | 'system' | 'logs' | 'settings';

interface BottomNavProps {
  currentTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  channelIssuesCount?: number;
  alertsCount?: number;
}

export const BottomNav: React.FC<BottomNavProps> = ({
  currentTab,
  onSelectTab,
  channelIssuesCount = 0,
  alertsCount = 0,
}) => {
  const isMoreActive = ['more', 'users', 'distribution', 'alerts', 'system', 'logs', 'settings'].includes(currentTab);

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-zinc-950/95 backdrop-blur-md border-t border-zinc-800/80 pb-safe">
      <div className="max-w-md mx-auto grid grid-cols-5 h-16 items-center px-1">
        {/* 1. Dashboard */}
        <button
          onClick={() => onSelectTab('dashboard')}
          className={`flex flex-col items-center justify-center h-full transition-colors ${
            currentTab === 'dashboard' ? 'text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'
          }`}
        >
          <LayoutDashboard className="w-5 h-5 mb-1" />
          <span className="text-[10px] font-medium tracking-tight">Asosiy</span>
        </button>

        {/* 2. Channels */}
        <button
          onClick={() => onSelectTab('channels')}
          className={`flex flex-col items-center justify-center h-full relative transition-colors ${
            currentTab === 'channels' ? 'text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'
          }`}
        >
          <div className="relative">
            <Radio className="w-5 h-5 mb-1" />
            {channelIssuesCount > 0 && (
              <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-red-500" />
            )}
          </div>
          <span className="text-[10px] font-medium tracking-tight">Kanallar</span>
        </button>

        {/* 3. Post Pool */}
        <button
          onClick={() => onSelectTab('posts')}
          className={`flex flex-col items-center justify-center h-full transition-colors ${
            currentTab === 'posts' ? 'text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'
          }`}
        >
          <Layers className="w-5 h-5 mb-1" />
          <span className="text-[10px] font-medium tracking-tight">Postlar</span>
        </button>

        {/* 4. Sources */}
        <button
          onClick={() => onSelectTab('sources')}
          className={`flex flex-col items-center justify-center h-full transition-colors ${
            currentTab === 'sources' ? 'text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'
          }`}
        >
          <Rss className="w-5 h-5 mb-1" />
          <span className="text-[10px] font-medium tracking-tight">Manbalar</span>
        </button>

        {/* 5. More */}
        <button
          onClick={() => onSelectTab('more')}
          className={`flex flex-col items-center justify-center h-full relative transition-colors ${
            isMoreActive ? 'text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'
          }`}
        >
          <div className="relative">
            <MoreHorizontal className="w-5 h-5 mb-1" />
            {alertsCount > 0 && (
              <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-amber-500" />
            )}
          </div>
          <span className="text-[10px] font-medium tracking-tight">Ko‘proq</span>
        </button>
      </div>
    </nav>
  );
};
