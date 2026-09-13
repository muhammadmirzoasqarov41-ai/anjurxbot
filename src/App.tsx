import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { FeedsView } from './components/FeedsView';
import { SubscribersView } from './components/SubscribersView';
import { PostsView } from './components/PostsView';
import { GuideView } from './components/GuideView';
import { RSSFeed, RSSSubscriber, DeliveredPost, RSSStats } from './types';

export default function App() {
  const [activeTab, setActiveTab] = useState<string>('feeds');
  const [feeds, setFeeds] = useState<RSSFeed[]>([]);
  const [subscribers, setSubscribers] = useState<RSSSubscriber[]>([]);
  const [posts, setPosts] = useState<DeliveredPost[]>([]);
  const [stats, setStats] = useState<RSSStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    loadAllData();
  }, []);

  const loadAllData = async () => {
    setLoading(true);
    try {
      await Promise.all([loadStats(), loadFeeds(), loadSubscribers(), loadPosts()]);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const res = await fetch('/api/stats');
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (e) {
      console.error('Failed to load stats', e);
    }
  };

  const loadFeeds = async () => {
    try {
      const res = await fetch('/api/feeds');
      if (res.ok) {
        const data = await res.json();
        setFeeds(data.feeds || []);
      }
    } catch (e) {
      console.error('Failed to load feeds', e);
    }
  };

  const loadSubscribers = async () => {
    try {
      const res = await fetch('/api/subscribers');
      if (res.ok) {
        const data = await res.json();
        setSubscribers(data.subscribers || []);
      }
    } catch (e) {
      console.error('Failed to load subscribers', e);
    }
  };

  const loadPosts = async () => {
    try {
      const res = await fetch('/api/posts');
      if (res.ok) {
        const data = await res.json();
        setPosts(data.posts || []);
      }
    } catch (e) {
      console.error('Failed to load posts', e);
    }
  };

  const handleAddFeed = async (url: string, title: string): Promise<boolean> => {
    try {
      const res = await fetch('/api/feeds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, title }),
      });
      if (res.ok) {
        await Promise.all([loadFeeds(), loadStats()]);
        return true;
      }
      return false;
    } catch (e) {
      console.error('Failed to add feed', e);
      return false;
    }
  };

  const handleDeleteFeed = async (feedId: string) => {
    try {
      const res = await fetch(`/api/feeds/${encodeURIComponent(feedId)}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        await Promise.all([loadFeeds(), loadStats(), loadSubscribers()]);
      }
    } catch (e) {
      console.error('Failed to delete feed', e);
    }
  };

  const handleSyncFeed = async (feedId: string) => {
    try {
      const res = await fetch(`/api/feeds/${encodeURIComponent(feedId)}/sync`, {
        method: 'POST',
      });
      if (res.ok) {
        await Promise.all([loadFeeds(), loadPosts()]);
      }
    } catch (e) {
      console.error('Failed to sync feed', e);
    }
  };

  const handleImportOpml = async (file: File) => {
    try {
      const text = await file.text();
      const res = await fetch('/api/import/opml', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ opml: text }),
      });
      if (res.ok) {
        await Promise.all([loadFeeds(), loadStats()]);
      }
    } catch (e) {
      console.error('Failed to import OPML', e);
    }
  };

  const handleExportOpml = () => {
    window.location.href = '/api/export/opml';
  };

  return (
    <div className="min-h-screen bg-black text-slate-100 flex flex-col font-sans">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        stats={stats}
        onRefresh={loadAllData}
        onExportOpml={handleExportOpml}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === 'feeds' && (
          <FeedsView
            feeds={feeds}
            stats={stats}
            onAddFeed={handleAddFeed}
            onDeleteFeed={handleDeleteFeed}
            onSyncFeed={handleSyncFeed}
            onImportOpml={handleImportOpml}
            loading={loading}
          />
        )}

        {activeTab === 'subscribers' && <SubscribersView subscribers={subscribers} />}

        {activeTab === 'posts' && <PostsView posts={posts} />}

        {activeTab === 'guide' && <GuideView />}
      </main>

      <footer className="border-t border-zinc-900 py-4 text-center text-xs text-zinc-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>AnjurX | Rss Bot &copy; 2026 — Ochiq manbali RSS/Atom Telegram boti</span>
          <div className="flex items-center space-x-4">
            <span>Holat: <strong className="text-emerald-400">FAOL</strong></span>
            <span>Versiya: <strong>3.0-RSS</strong></span>
          </div>
        </div>
      </footer>
    </div>
  );
}
