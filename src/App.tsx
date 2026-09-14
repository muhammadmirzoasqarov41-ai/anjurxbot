import React, { useState, useEffect } from 'react';
import { api } from './api';
import { AuthUser, DashboardData } from './types';
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
import { ArrowLeft } from 'lucide-react';

const SUPER_ADMIN_USER: AuthUser = {
  user_id: 8157452043,
  role: 'super_admin',
  name: 'Super Admin',
};

export default function App() {
  const [currentUser] = useState<AuthUser>(SUPER_ADMIN_USER);
  const [currentTab, setCurrentTab] = useState<NavTab>('dashboard');
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [isMoreMenuOpen, setIsMoreMenuOpen] = useState(false);

  // Fetch Dashboard data
  const fetchDashboardData = async () => {
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
    fetchDashboardData();
    // Periodic 20s polling for live dashboard metrics
    const interval = setInterval(fetchDashboardData, 20000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectTab = (tab: NavTab) => {
    if (tab === 'more') {
      setIsMoreMenuOpen(true);
    } else {
      setCurrentTab(tab);
    }
  };

  const isSubView = ['users', 'distribution', 'system', 'logs', 'settings'].includes(currentTab);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col antialiased selection:bg-emerald-500 selection:text-zinc-950">
      {/* Top Header */}
      <Header
        user={currentUser}
        botStatus={dashboardData?.pulse?.bot || 'standby'}
        refreshing={refreshing}
        onRefresh={fetchDashboardData}
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
      />
    </div>
  );
}
