import React, { useState, useEffect } from 'react';
import { api } from './api';
import { AuthUser, DashboardData } from './types';
import { LoginPage } from './components/LoginPage';
import { Header } from './components/Header';
import { BottomNav, NavTab } from './components/BottomNav';
import { DashboardView } from './components/DashboardView';
import { ChannelsView } from './components/ChannelsView';
import { PostsPoolView } from './components/PostsPoolView';
import { SourcesView } from './components/SourcesView';
import { UsersView } from './components/UsersView';
import { DistributionView } from './components/DistributionView';
import { SystemView } from './components/SystemView';
import { LogsView } from './components/LogsView';
import { SettingsView } from './components/SettingsView';
import { MoreMenuModal } from './components/MoreMenuModal';
import { ArrowLeft, ShieldCheck } from 'lucide-react';

export default function App() {
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [currentTab, setCurrentTab] = useState<NavTab>('dashboard');
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [isMoreMenuOpen, setIsMoreMenuOpen] = useState(false);

  // Validate or restore session on load
  useEffect(() => {
    let isMounted = true;
    api.getSession()
      .then((session) => {
        if (isMounted) {
          if (session && session.authenticated && session.user) {
            setCurrentUser(session.user);
          } else {
            setCurrentUser(null);
          }
        }
      })
      .catch(() => {
        if (isMounted) {
          setCurrentUser(null);
        }
      })
      .finally(() => {
        if (isMounted) {
          setAuthChecking(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Fetch Dashboard data only when user is authenticated
  const fetchDashboardData = async () => {
    if (!currentUser) return;
    setRefreshing(true);
    try {
      const data = await api.getDashboard();
      setDashboardData(data);
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (!currentUser) return;
    fetchDashboardData();
    // Periodic 20s polling for live dashboard metrics
    const interval = setInterval(fetchDashboardData, 20000);
    return () => clearInterval(interval);
  }, [currentUser]);

  const handleLogout = async () => {
    try {
      await api.logout();
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setCurrentUser(null);
      setDashboardData(null);
      setCurrentTab('dashboard');
    }
  };

  const handleSelectTab = (tab: NavTab) => {
    if (tab === 'more') {
      setIsMoreMenuOpen(true);
    } else {
      setCurrentTab(tab);
    }
  };

  // 1. Loading session screen
  if (authChecking) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col justify-center items-center px-4">
        <div className="flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-emerald-400 animate-pulse">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <p className="text-xs text-zinc-400 font-medium">Xavfsiz sessiya tekshirilmoqda...</p>
        </div>
      </div>
    );
  }

  // 2. Unauthenticated: Render real Web Admin Panel Login page
  if (!currentUser) {
    return (
      <LoginPage
        onLoginSuccess={(user) => {
          setCurrentUser(user);
        }}
      />
    );
  }

  const isSubView = ['users', 'distribution', 'system', 'logs', 'settings'].includes(currentTab);

  // 3. Authenticated: Render real Admin Dashboard Control Center
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col antialiased selection:bg-emerald-500 selection:text-zinc-950">
      {/* Top Header */}
      <Header
        user={currentUser}
        botStatus={dashboardData?.pulse?.bot || 'standby'}
        refreshing={refreshing}
        onRefresh={fetchDashboardData}
        onLogout={handleLogout}
        hasAlerts={(dashboardData?.alerts?.length || 0) > 0}
        onOpenAlerts={() => setCurrentTab('channels')}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-4xl w-full mx-auto px-4 pt-4 sm:pt-6">
        {/* Sub-view Back Button */}
        {isSubView && (
          <div className="mb-4">
            <button
              onClick={() => setCurrentTab('dashboard')}
              className="inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-white bg-zinc-900 border border-zinc-800 px-3 py-1.5 rounded-xl transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Bosh sahifaga qaytish</span>
            </button>
          </div>
        )}

        {/* View Switcher */}
        {currentTab === 'dashboard' && (
          <DashboardView
            data={dashboardData}
            loading={refreshing}
            onNavigate={(tab) => setCurrentTab(tab)}
            onRefresh={fetchDashboardData}
          />
        )}

        {currentTab === 'channels' && (
          <ChannelsView onRefresh={fetchDashboardData} />
        )}

        {currentTab === 'posts' && (
          <PostsPoolView onRefresh={fetchDashboardData} />
        )}

        {currentTab === 'sources' && (
          <SourcesView onRefresh={fetchDashboardData} />
        )}

        {currentTab === 'users' && (
          <UsersView onRefresh={fetchDashboardData} />
        )}

        {currentTab === 'distribution' && (
          <DistributionView onRefresh={fetchDashboardData} />
        )}

        {currentTab === 'system' && (
          <SystemView />
        )}

        {currentTab === 'logs' && (
          <LogsView />
        )}

        {currentTab === 'settings' && (
          <SettingsView />
        )}
      </main>

      {/* Mobile Bottom Navigation */}
      <BottomNav
        currentTab={currentTab}
        onSelectTab={handleSelectTab}
        channelIssuesCount={dashboardData?.metrics?.permission_issues || 0}
        alertsCount={dashboardData?.alerts?.length || 0}
      />

      {/* More Options Bottom Sheet / Modal */}
      <MoreMenuModal
        isOpen={isMoreMenuOpen}
        onClose={() => setIsMoreMenuOpen(false)}
        onSelectTab={(tab) => setCurrentTab(tab)}
        onLogout={handleLogout}
      />
    </div>
  );
}
