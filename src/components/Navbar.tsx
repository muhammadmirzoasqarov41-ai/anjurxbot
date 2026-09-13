import React from 'react';
import { Rss, Users, Send, BookOpen, Download, RefreshCw } from 'lucide-react';
import { RSSStats } from '../types';

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  stats: RSSStats | null;
  onRefresh: () => void;
  onExportOpml: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  stats,
  onRefresh,
  onExportOpml,
}) => {
  return (
    <header className="sticky top-0 z-40 bg-zinc-950/90 backdrop-blur border-b border-zinc-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-orange-500/10 border border-orange-500/30 flex items-center justify-center text-orange-400 shadow-sm shadow-orange-500/10">
            <Rss className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-white text-base tracking-tight">AnjurX | Rss Bot</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-orange-500/20 text-orange-400 border border-orange-500/30">
                v3.0 RSS
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 leading-none mt-0.5">
              Tezkor Telegram RSS/Atom/JSON Lentalar Boshqaruv Markazi
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center space-x-1">
          <button
            id="tab-feeds-btn"
            onClick={() => setActiveTab('feeds')}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-md text-xs font-semibold transition-colors ${
              activeTab === 'feeds'
                ? 'bg-orange-500/15 text-orange-400 border border-orange-500/30'
                : 'text-zinc-400 hover:text-white hover:bg-zinc-900'
            }`}
          >
            <Rss className="w-4 h-4" />
            <span>Lentalar (Feeds)</span>
          </button>

          <button
            id="tab-subscribers-btn"
            onClick={() => setActiveTab('subscribers')}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-md text-xs font-semibold transition-colors ${
              activeTab === 'subscribers'
                ? 'bg-orange-500/15 text-orange-400 border border-orange-500/30'
                : 'text-zinc-400 hover:text-white hover:bg-zinc-900'
            }`}
          >
            <Users className="w-4 h-4" />
            <span>Obunachilar</span>
          </button>

          <button
            id="tab-posts-btn"
            onClick={() => setActiveTab('posts')}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-md text-xs font-semibold transition-colors ${
              activeTab === 'posts'
                ? 'bg-orange-500/15 text-orange-400 border border-orange-500/30'
                : 'text-zinc-400 hover:text-white hover:bg-zinc-900'
            }`}
          >
            <Send className="w-4 h-4" />
            <span>Yetkazilgan Postlar</span>
          </button>

          <button
            id="tab-guide-btn"
            onClick={() => setActiveTab('guide')}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-md text-xs font-semibold transition-colors ${
              activeTab === 'guide'
                ? 'bg-orange-500/15 text-orange-400 border border-orange-500/30'
                : 'text-zinc-400 hover:text-white hover:bg-zinc-900'
            }`}
          >
            <BookOpen className="w-4 h-4" />
            <span>Buyruqlar & Qo'llanma</span>
          </button>
        </nav>

        {/* Action Controls */}
        <div className="flex items-center space-x-2">
          <div className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-[11px] text-zinc-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="text-zinc-400">Gardener:</span>
            <span className="font-semibold text-emerald-400">FAOL</span>
          </div>

          <button
            id="btn-export-opml"
            onClick={onExportOpml}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-700 transition"
            title="OPML formatida eksport qilish"
          >
            <Download className="w-3.5 h-3.5 text-zinc-400" />
            <span className="hidden sm:inline">OPML Eksport</span>
          </button>

          <button
            id="btn-refresh-all"
            onClick={onRefresh}
            className="p-1.5 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-900 border border-zinc-800 transition"
            title="Ma'lumotlarni yangilash"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Mobile navigation tab bar */}
      <div className="flex md:hidden border-t border-zinc-800/80 px-2 py-1.5 overflow-x-auto gap-1 bg-zinc-950">
        <button
          onClick={() => setActiveTab('feeds')}
          className={`flex items-center space-x-1 px-3 py-1 rounded text-xs whitespace-nowrap ${
            activeTab === 'feeds' ? 'bg-orange-500/20 text-orange-400 font-semibold' : 'text-zinc-400'
          }`}
        >
          <Rss className="w-3.5 h-3.5" />
          <span>Lentalar</span>
        </button>
        <button
          onClick={() => setActiveTab('subscribers')}
          className={`flex items-center space-x-1 px-3 py-1 rounded text-xs whitespace-nowrap ${
            activeTab === 'subscribers' ? 'bg-orange-500/20 text-orange-400 font-semibold' : 'text-zinc-400'
          }`}
        >
          <Users className="w-3.5 h-3.5" />
          <span>Obunachilar</span>
        </button>
        <button
          onClick={() => setActiveTab('posts')}
          className={`flex items-center space-x-1 px-3 py-1 rounded text-xs whitespace-nowrap ${
            activeTab === 'posts' ? 'bg-orange-500/20 text-orange-400 font-semibold' : 'text-zinc-400'
          }`}
        >
          <Send className="w-3.5 h-3.5" />
          <span>Postlar</span>
        </button>
        <button
          onClick={() => setActiveTab('guide')}
          className={`flex items-center space-x-1 px-3 py-1 rounded text-xs whitespace-nowrap ${
            activeTab === 'guide' ? 'bg-orange-500/20 text-orange-400 font-semibold' : 'text-zinc-400'
          }`}
        >
          <BookOpen className="w-3.5 h-3.5" />
          <span>Qo'llanma</span>
        </button>
      </div>
    </header>
  );
};
