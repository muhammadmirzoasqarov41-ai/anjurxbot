import React from 'react';
import { Shield, Users, AlertTriangle, PlayCircle, BarChart3, Terminal, UserCheck, RefreshCw } from 'lucide-react';

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  onLogout: () => void;
  authenticated: boolean;
  botStatus?: string;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  onLogout,
  authenticated,
  botStatus = 'running',
}) => {
  const tabs = [
    { id: 'dashboard', label: 'Boshqaruv (Dashboard)', icon: BarChart3 },
    { id: 'guard', label: 'Guruhlar & Qorovul', icon: Shield },
    { id: 'users', label: 'Foydalanuvchilar', icon: Users },
    { id: 'moderation', label: 'Moderatsiya Jurnali', icon: AlertTriangle },
    { id: 'simulator', label: 'Qorovul Sinovchi', icon: PlayCircle },
  ];

  return (
    <header className="bg-[#070b12] border-b border-[#152033] sticky top-0 z-40 font-mono-cyber">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#0d1522] border border-[#00ff66]/40 flex items-center justify-center text-[#00ff66] shadow-[0_0_12px_rgba(0,255,102,0.2)]">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-base text-white tracking-wider">ANJURX_BOT</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#00ff66]/10 text-[#00ff66] border border-[#00ff66]/30 font-semibold">
                  QOROVUL_CENTER
                </span>
              </div>
              <p className="text-[11px] text-slate-500 hidden sm:block">
                Telegram Guruhingizning Qorovuli (Group Guard & Protection System)
              </p>
            </div>
          </div>

          {/* Center Navigation Tabs */}
          <nav className="hidden lg:flex space-x-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  id={`nav-tab-${tab.id}`}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all duration-150 cursor-pointer ${
                    isActive
                      ? 'bg-[#00ff66]/10 text-[#00ff66] border border-[#00ff66]/40 shadow-[0_0_10px_rgba(0,255,102,0.15)]'
                      : 'text-slate-400 hover:text-white hover:bg-[#0f1726]'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Right Status & Controls */}
          <div className="flex items-center gap-3">
            {/* Live Polling Status */}
            <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 bg-[#09131e] border border-[#1b2b40] rounded-full text-[11px]">
              <span
                className={`w-2 h-2 rounded-full ${
                  botStatus === 'running'
                    ? 'bg-[#00ff66] animate-pulse shadow-[0_0_8px_#00ff66]'
                    : 'bg-amber-400'
                }`}
              />
              <span className="text-slate-300">
                {botStatus === 'running' ? 'LIVE POLLING' : 'STANDBY'}
              </span>
            </div>

            {/* Super Admin Badge */}
            <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 bg-[#09131e] border border-[#1b2b40] rounded-lg text-[11px] text-slate-300">
              <UserCheck className="w-3.5 h-3.5 text-[#00ff66]" />
              <span>@usafes [8157452043]</span>
            </div>

            {/* Refresh Data Button */}
            <button
              id="btn-refresh"
              onClick={onLogout}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[#00ff66] hover:text-white bg-[#0d1522] hover:bg-[#00ff66]/20 border border-[#00ff66]/30 rounded-lg transition-all cursor-pointer"
              title="Barcha ma'lumotlarni yangilash"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Yangilash</span>
            </button>
          </div>
        </div>

        {/* Mobile Navigation */}
        <div className="flex lg:hidden overflow-x-auto py-2 space-x-1.5 border-t border-[#152033] scrollbar-none">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap cursor-pointer ${
                  isActive
                    ? 'bg-[#00ff66]/10 text-[#00ff66] border border-[#00ff66]/40'
                    : 'text-slate-400 hover:text-white bg-[#0a0f1a]'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </header>
  );
};
