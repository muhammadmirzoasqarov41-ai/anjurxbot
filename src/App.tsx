import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { DashboardView } from './components/DashboardView';
import { UsersView } from './components/UsersView';
import { GuardView } from './components/GuardView';
import { ForceSubView } from './components/ForceSubView';
import { ModerationView } from './components/ModerationView';
import { SimulatorView } from './components/SimulatorView';
import { LoginModal } from './components/LoginModal';
import { TelegramUser, TelegramGroup, ModerationLog, SystemStats, GuardSettings, ForceSubChannel } from './types';

export default function App() {
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [authenticated, setAuthenticated] = useState<boolean>(true);
  const [loginModalOpen, setLoginModalOpen] = useState<boolean>(false);

  const [stats, setStats] = useState<SystemStats | null>(null);
  const [users, setUsers] = useState<TelegramUser[]>([]);
  const [totalUsers, setTotalUsers] = useState<number>(0);
  const [userPage, setUserPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [userSearch, setUserSearch] = useState<string>('');

  const [groups, setGroups] = useState<TelegramGroup[]>([]);
  const [moderationLogs, setModerationLogs] = useState<ModerationLog[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Check auth and load initial state
  useEffect(() => {
    checkAuth();
    loadAllData();
  }, []);

  const checkAuth = async () => {
    try {
      const res = await fetch('/api/auth/me');
      if (res.ok) {
        const data = await res.json();
        setAuthenticated(data.authenticated);
      }
    } catch (e) {
      console.error('Auth check error', e);
    }
  };

  const loadAllData = async () => {
    setLoading(true);
    try {
      await Promise.all([loadStats(), loadUsers(1, ''), loadGroups(), loadModerationLogs()]);
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

  const loadUsers = async (page = 1, search = '') => {
    try {
      const query = new URLSearchParams({
        page: String(page),
        limit: '50',
        search,
      });
      const res = await fetch(`/api/users?${query}`);
      if (res.ok) {
        const data = await res.json();
        setUsers(data.users || []);
        setTotalUsers(data.total || 0);
        setUserPage(data.page || 1);
        setTotalPages(data.total_pages || 1);
      }
    } catch (e) {
      console.error('Failed to load users', e);
    }
  };

  const loadGroups = async () => {
    try {
      const res = await fetch('/api/groups');
      if (res.ok) {
        const data = await res.json();
        setGroups(data.groups || []);
      }
    } catch (e) {
      console.error('Failed to load groups', e);
    }
  };

  const loadModerationLogs = async () => {
    try {
      const res = await fetch('/api/moderation');
      if (res.ok) {
        const data = await res.json();
        setModerationLogs(data.logs || []);
      }
    } catch (e) {
      console.error('Failed to load moderation logs', e);
    }
  };

  const handleLogout = async () => {
    try {
      await fetch('/api/logout', { method: 'POST' });
      setAuthenticated(false);
      setLoginModalOpen(true);
    } catch (e) {
      console.error(e);
    }
  };

  const handleClearWarns = async (userId: number) => {
    try {
      const res = await fetch('/api/moderation/clearwarns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId }),
      });
      if (res.ok) {
        await Promise.all([loadUsers(userPage, userSearch), loadModerationLogs(), loadStats()]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddUser = async (user: Partial<TelegramUser>) => {
    try {
      const res = await fetch('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(user),
      });
      if (res.ok) {
        await Promise.all([loadUsers(1, ''), loadStats()]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleUpdateGuard = async (groupId: string, guard: GuardSettings) => {
    try {
      const res = await fetch(`/api/groups/${groupId}/guard`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(guard),
      });
      if (res.ok) {
        await Promise.all([loadGroups(), loadStats()]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddChannel = async (groupId: string, channel: Partial<ForceSubChannel>) => {
    try {
      const res = await fetch(`/api/groups/${groupId}/fsub`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(channel),
      });
      if (res.ok) {
        await loadGroups();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRemoveChannel = async (groupId: string, channelId: string | number) => {
    try {
      const res = await fetch(`/api/groups/${groupId}/fsub/${channelId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        await loadGroups();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSimulateMessage = async (groupId: number, text: string, username: string) => {
    try {
      const res = await fetch('/api/bot/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          group_id: groupId,
          message_text: text,
          username,
        }),
      });
      const data = await res.json();
      await Promise.all([loadModerationLogs(), loadUsers(userPage, userSearch), loadStats()]);
      return data;
    } catch (e) {
      console.error(e);
      return { allowed: false, action: 'error', reason: 'Tarmoq xatosi' };
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onLogout={handleLogout}
        authenticated={authenticated}
        onOpenLogin={() => setLoginModalOpen(true)}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'dashboard' && (
          <DashboardView
            stats={stats}
            groups={groups}
            recentLogs={moderationLogs}
            onNavigate={setActiveTab}
          />
        )}

        {activeTab === 'users' && (
          <UsersView
            users={users}
            totalUsers={totalUsers}
            page={userPage}
            totalPages={totalPages}
            onPageChange={(newPage) => {
              setUserPage(newPage);
              loadUsers(newPage, userSearch);
            }}
            onSearch={(query) => {
              setUserSearch(query);
              loadUsers(1, query);
            }}
            onClearWarns={handleClearWarns}
            onAddUser={handleAddUser}
          />
        )}

        {activeTab === 'guard' && (
          <GuardView groups={groups} onUpdateGuard={handleUpdateGuard} />
        )}

        {activeTab === 'fsub' && (
          <ForceSubView
            groups={groups}
            onAddChannel={handleAddChannel}
            onRemoveChannel={handleRemoveChannel}
          />
        )}

        {activeTab === 'moderation' && (
          <ModerationView logs={moderationLogs} onClearWarns={handleClearWarns} />
        )}

        {activeTab === 'simulator' && (
          <SimulatorView
            groups={groups}
            onSimulateMessage={handleSimulateMessage}
          />
        )}
      </main>

      <footer className="border-t border-slate-900 bg-slate-950/80 py-6 text-center text-xs text-slate-500">
        <p>AnjurXBot &bull; Telegram Guruhi Xavfsizlik & Moderatsiya Tizimi &bull; 2026</p>
      </footer>

      <LoginModal
        isOpen={loginModalOpen}
        onClose={() => setLoginModalOpen(false)}
        onLoginSuccess={() => {
          setAuthenticated(true);
          loadAllData();
        }}
      />
    </div>
  );
}
