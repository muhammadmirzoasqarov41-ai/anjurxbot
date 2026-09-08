import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { DashboardView } from './components/DashboardView';
import { UsersView } from './components/UsersView';
import { GuardView } from './components/GuardView';
import { ForceSubView } from './components/ForceSubView';
import { ModerationView } from './components/ModerationView';
import { SimulatorView } from './components/SimulatorView';
import { LoginView } from './components/LoginView';
import { TelegramUser, TelegramGroup, ModerationLog, SystemStats, GuardSettings, ForceSubChannel } from './types';

export default function App() {
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [authenticated, setAuthenticated] = useState<boolean | null>(null); // null = checking

  const [stats, setStats] = useState<SystemStats | null>(null);
  const [users, setUsers] = useState<TelegramUser[]>([]);
  const [totalUsers, setTotalUsers] = useState<number>(0);
  const [userPage, setUserPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [userSearch, setUserSearch] = useState<string>('');

  const [groups, setGroups] = useState<TelegramGroup[]>([]);
  const [moderationLogs, setModerationLogs] = useState<ModerationLog[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [botStatus, setBotStatus] = useState<string>('running');

  // Check auth and sync state
  useEffect(() => {
    checkAuth();
  }, []);

  const getHeaders = (customHeaders: Record<string, string> = {}) => {
    const token = localStorage.getItem('anjurx_token');
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...customHeaders,
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  };

  const checkAuth = async () => {
    try {
      const res = await fetch('/api/auth/session', {
        headers: getHeaders(),
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        setAuthenticated(data.authenticated);
        if (data.authenticated) {
          loadAllData();
        }
      } else {
        setAuthenticated(false);
      }
    } catch (e) {
      setAuthenticated(false);
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
      const res = await fetch('/api/admin/dashboard', {
        headers: getHeaders(),
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        setStats(data);
        if (data.bot_status) {
          setBotStatus(data.bot_status);
        }
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
      const res = await fetch(`/api/admin/users?${query}`, {
        headers: getHeaders(),
        credentials: 'include',
      });
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
      const res = await fetch('/api/admin/groups', {
        headers: getHeaders(),
        credentials: 'include',
      });
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
      const res = await fetch('/api/admin/logs', {
        headers: getHeaders(),
        credentials: 'include',
      });
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
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: getHeaders(),
        credentials: 'include',
      });
    } catch (e) {
      console.error(e);
    } finally {
      localStorage.removeItem('anjurx_token');
      localStorage.removeItem('anjurx_user');
      setAuthenticated(false);
      window.history.pushState(null, '', '/');
    }
  };

  const handleLoginSuccess = () => {
    setAuthenticated(true);
    window.history.pushState(null, '', '/admin');
    loadAllData();
  };

  const handleClearWarns = async (userId: number) => {
    try {
      const res = await fetch('/api/admin/logs/clearwarns', {
        method: 'POST',
        headers: getHeaders(),
        credentials: 'include',
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
        headers: getHeaders(),
        credentials: 'include',
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
      const res = await fetch(`/api/admin/groups/${groupId}/guard`, {
        method: 'PUT',
        headers: getHeaders(),
        credentials: 'include',
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
      const res = await fetch(`/api/admin/groups/${groupId}/fsub`, {
        method: 'POST',
        headers: getHeaders(),
        credentials: 'include',
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
      const res = await fetch(`/api/admin/groups/${groupId}/fsub/${channelId}`, {
        method: 'DELETE',
        headers: getHeaders(),
        credentials: 'include',
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
        headers: getHeaders(),
        credentials: 'include',
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

  // Checking initial auth state spinner
  if (authenticated === null) {
    return (
      <div className="min-h-screen bg-[#05070a] flex items-center justify-center font-mono-cyber">
        <div className="text-center">
          <div className="w-10 h-10 border-2 border-[#00ff66] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <div className="text-xs text-[#00ff66] tracking-wider uppercase font-semibold">
            Connecting Security Gateway...
          </div>
        </div>
      </div>
    );
  }

  // Not authenticated: Render Fullscreen Cyber Admin Login View
  if (!authenticated) {
    return <LoginView onLoginSuccess={handleLoginSuccess} />;
  }

  // Authenticated: Render Cyber Control Center Dashboard
  return (
    <div className="min-h-screen bg-cyber-grid text-slate-100 flex flex-col font-sans">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onLogout={handleLogout}
        authenticated={authenticated}
        botStatus={botStatus}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'dashboard' && (
          <DashboardView
            stats={stats}
            groups={groups}
            recentLogs={moderationLogs}
            onNavigate={setActiveTab}
            onRefresh={loadAllData}
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

      <footer className="border-t border-[#121c2b] bg-[#05070a]/90 py-5 text-center text-xs text-slate-500 font-mono-cyber">
        <div className="flex items-center justify-center gap-4">
          <span>ANJURX_BOT PROTOCOL V2.4</span>
          <span>&bull;</span>
          <span>SUPER ADMIN: @usafes [8157452043]</span>
          <span>&bull;</span>
          <span className="text-[#00ff66]">PROTECTION ACTIVE</span>
        </div>
      </footer>
    </div>
  );
}
