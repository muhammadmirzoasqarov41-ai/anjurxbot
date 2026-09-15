import React from 'react';
import { AuthUser } from '../types';
import { Bot, RefreshCw, LogOut, ShieldAlert } from 'lucide-react';

interface HeaderProps {
  user: AuthUser | null;
  botStatus: 'online' | 'standby' | 'error';
  refreshing: boolean;
  onRefresh: () => void;
  onLogout?: () => void;
  hasAlerts?: boolean;
  onOpenAlerts?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  user,
  botStatus,
  refreshing,
  onRefresh,
  onLogout,
  hasAlerts,
  onOpenAlerts,
}) => {
  return (
    <header className="sticky top-0 z-30 bg-zinc-950/90 backdrop-blur-md border-b border-zinc-800/80 px-4 py-3">
      <div className="max-w-6xl mx-auto flex items-center justify-between">
        {/* Left: Brand & Bot Status */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-sm">
              AX
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-sm font-semibold text-white tracking-tight">AnjurX</h1>
                <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  Super Admin
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-[11px] text-zinc-400">
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    botStatus === 'online'
                      ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]'
                      : botStatus === 'standby'
                      ? 'bg-amber-400'
                      : 'bg-red-400'
                  }`}
                />
                <span className="capitalize">
                  {botStatus === 'online' ? 'Bot Faol' : botStatus === 'standby' ? 'Standby' : 'Xatolik'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2">
          {/* Alerts button if there are alerts */}
          {hasAlerts && onOpenAlerts && (
            <button
              onClick={onOpenAlerts}
              title="Ogohlantirishlar"
              className="relative p-2 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 transition-colors"
            >
              <ShieldAlert className="w-4 h-4 animate-pulse" />
              <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-red-500" />
            </button>
          )}

          {/* Refresh Button */}
          <button
            onClick={onRefresh}
            disabled={refreshing}
            title="Yangilash"
            className="p-2 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white hover:bg-zinc-800 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-emerald-400' : ''}`} />
          </button>

          {/* Logout Button */}
          {onLogout && (
            <button
              onClick={onLogout}
              title="Tizimdan chiqish"
              className="p-2 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-red-400 hover:bg-red-500/10 hover:border-red-500/30 transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
