import React from 'react';
import { DashboardData } from '../types';
import {
  Radio,
  Send,
  Layers,
  Users,
  Rss,
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  Clock,
  HardDrive,
  Activity,
  ArrowUpRight,
  ShieldAlert,
} from 'lucide-react';

interface DashboardViewProps {
  data: DashboardData | null;
  loading: boolean;
  onNavigate: (tab: any) => void;
  onRefresh: () => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  data,
  loading,
  onNavigate,
  onRefresh,
}) => {
  if (loading && !data) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-zinc-500">
        <Activity className="w-8 h-8 animate-spin text-emerald-500 mb-3" />
        <p className="text-sm font-medium">Bosh sahifa ma'lumotlari yuklanmoqda...</p>
      </div>
    );
  }

  const metrics = data?.metrics || {
    total_channels: 0,
    active_channels: 0,
    permission_issues: 0,
    total_sources: 0,
    active_sources: 0,
    error_sources: 0,
    total_users: 0,
    contract_users: 0,
    posts_delivered_today: 0,
    total_delivered: 0,
    pool_queued: 0,
    pool_delivered: 0,
    pool_expired: 0,
    pool_total: 0,
  };

  const pulse = data?.pulse || {
    bot: 'standby',
    gardener: 'stopped',
    storage_mode: 'N/A',
    uptime_seconds: 0,
    last_sync: '',
  };

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (hours > 0) return `${hours} soat ${mins} daqiqa`;
    return `${mins} daqiqa`;
  };

  const formatTimeAgo = (isoString: string) => {
    if (!isoString) return 'N/A';
    try {
      const diffMs = Date.now() - new Date(isoString).getTime();
      const diffMins = Math.floor(diffMs / 60000);
      if (diffMins < 1) return 'Hozirgina';
      if (diffMins < 60) return `${diffMins} daqiqa oldin`;
      const diffHours = Math.floor(diffMins / 60);
      if (diffHours < 24) return `${diffHours} soat oldin`;
      return new Date(isoString).toLocaleDateString('uz-UZ');
    } catch {
      return isoString;
    }
  };

  return (
    <div className="space-y-6 pb-20">
      {/* 1. System Pulse Bar */}
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300 uppercase tracking-wider">
            <Activity className="w-3.5 h-3.5 text-emerald-400" />
            <span>Tizim Holati (Pulse)</span>
          </div>
          <span className="text-[11px] text-zinc-500 font-mono">
            Ish vaqti: {formatUptime(pulse.uptime_seconds)}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          {/* Bot Polling */}
          <div className="bg-zinc-950/60 border border-zinc-800/80 rounded-xl p-2.5">
            <span className="text-[10px] text-zinc-500 block mb-1">Telegram Bot</span>
            <div className="flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  pulse.bot === 'online' ? 'bg-emerald-400' : 'bg-amber-400'
                }`}
              />
              <span className="text-xs font-medium text-white capitalize">
                {pulse.bot === 'online' ? 'Faol (Polling)' : 'Kutishda'}
              </span>
            </div>
          </div>

          {/* Gardener Worker */}
          <div className="bg-zinc-950/60 border border-zinc-800/80 rounded-xl p-2.5">
            <span className="text-[10px] text-zinc-500 block mb-1">Gardener Servisi</span>
            <div className="flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  pulse.gardener === 'running' ? 'bg-emerald-400' : 'bg-red-400'
                }`}
              />
              <span className="text-xs font-medium text-white capitalize">
                {pulse.gardener === 'running' ? 'Avtomatik' : 'To‘xtagan'}
              </span>
            </div>
          </div>

          {/* Storage Mode */}
          <div className="bg-zinc-950/60 border border-zinc-800/80 rounded-xl p-2.5">
            <span className="text-[10px] text-zinc-500 block mb-1">Ma'lumotlar Bazasi</span>
            <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-200 truncate">
              <HardDrive className="w-3 h-3 text-emerald-400 shrink-0" />
              <span className="truncate">{pulse.storage_mode}</span>
            </div>
          </div>

          {/* Distribution Engine */}
          <div className="bg-zinc-950/60 border border-zinc-800/80 rounded-xl p-2.5">
            <span className="text-[10px] text-zinc-500 block mb-1">Taqsimot Qoidasi</span>
            <span className="text-xs font-medium text-emerald-300">Fair Distribution</span>
          </div>
        </div>
      </div>

      {/* 2. Critical Alerts Banner if any */}
      {data?.alerts && data.alerts.length > 0 && (
        <div className="space-y-2">
          {data.alerts.map((alert) => (
            <div
              key={alert.id}
              className={`p-3.5 rounded-2xl border flex items-start justify-between gap-3 ${
                alert.severity === 'critical'
                  ? 'bg-red-950/30 border-red-900/60 text-red-200'
                  : 'bg-amber-950/30 border-amber-900/60 text-amber-200'
              }`}
            >
              <div className="flex items-start gap-2.5">
                <ShieldAlert
                  className={`w-5 h-5 shrink-0 mt-0.5 ${
                    alert.severity === 'critical' ? 'text-red-400' : 'text-amber-400'
                  }`}
                />
                <div>
                  <h4 className="text-xs font-bold">{alert.title}</h4>
                  <p className="text-[11px] opacity-90 mt-0.5">{alert.message}</p>
                </div>
              </div>
              <button
                onClick={() => onNavigate(alert.action === 'check_channels' ? 'channels' : 'sources')}
                className="px-2.5 py-1 bg-zinc-900 border border-zinc-700 text-xs font-medium rounded-lg text-white shrink-0 hover:bg-zinc-800 transition-colors"
              >
                Ko‘rish
              </button>
            </div>
          ))}
        </div>
      )}

      {/* 3. Top-Level Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {/* Active Channels */}
        <div
          onClick={() => onNavigate('channels')}
          className="bg-zinc-900/80 border border-zinc-800 hover:border-zinc-700 rounded-2xl p-4 cursor-pointer transition-all active:scale-[0.98]"
        >
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs font-medium">Faol Kanallar</span>
            <Radio className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-bold text-white tracking-tight">
              {metrics.active_channels}
            </span>
            <span className="text-xs text-zinc-500">/ {metrics.total_channels} ta</span>
          </div>
          {metrics.permission_issues > 0 ? (
            <p className="text-[11px] text-red-400 mt-1 font-medium">
              {metrics.permission_issues} ta kanalda ruxsat xatosi
            </p>
          ) : (
            <p className="text-[11px] text-emerald-400 mt-1 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" /> Barchasi normal
            </p>
          )}
        </div>

        {/* Delivered Today */}
        <div
          onClick={() => onNavigate('distribution')}
          className="bg-zinc-900/80 border border-zinc-800 hover:border-zinc-700 rounded-2xl p-4 cursor-pointer transition-all active:scale-[0.98]"
        >
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs font-medium">Bugun Yetkazilgan</span>
            <Send className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-bold text-white tracking-tight">
              {metrics.posts_delivered_today}
            </span>
            <span className="text-xs text-zinc-500">post</span>
          </div>
          <p className="text-[11px] text-zinc-400 mt-1">
            Jami: <strong className="text-zinc-200">{metrics.total_delivered}</strong>
          </p>
        </div>

        {/* Post Pool Queued */}
        <div
          onClick={() => onNavigate('posts')}
          className="bg-zinc-900/80 border border-zinc-800 hover:border-zinc-700 rounded-2xl p-4 cursor-pointer transition-all active:scale-[0.98]"
        >
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs font-medium">Navbatdagi Postlar</span>
            <Layers className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-bold text-white tracking-tight">
              {metrics.pool_queued}
            </span>
            <span className="text-xs text-zinc-500">/ {metrics.pool_total} jami</span>
          </div>
          <p className="text-[11px] text-zinc-400 mt-1">5 kunlik retention hovuzi</p>
        </div>

        {/* RSS Sources */}
        <div
          onClick={() => onNavigate('sources')}
          className="bg-zinc-900/80 border border-zinc-800 hover:border-zinc-700 rounded-2xl p-4 cursor-pointer transition-all active:scale-[0.98]"
        >
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs font-medium">RSS Manbalar</span>
            <Rss className="w-4 h-4 text-amber-400" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-bold text-white tracking-tight">
              {metrics.active_sources}
            </span>
            <span className="text-xs text-zinc-500">/ {metrics.total_sources} ta</span>
          </div>
          {metrics.error_sources > 0 ? (
            <p className="text-[11px] text-amber-400 mt-1">
              {metrics.error_sources} ta manbada xatolik
            </p>
          ) : (
            <p className="text-[11px] text-emerald-400 mt-1">Barcha manbalar faol</p>
          )}
        </div>

        {/* Users / Plans */}
        <div
          onClick={() => onNavigate('users')}
          className="bg-zinc-900/80 border border-zinc-800 hover:border-zinc-700 rounded-2xl p-4 cursor-pointer transition-all active:scale-[0.98]"
        >
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs font-medium">Foydalanuvchilar</span>
            <Users className="w-4 h-4 text-blue-400" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-bold text-white tracking-tight">
              {metrics.total_users}
            </span>
            <span className="text-xs text-zinc-500">ta</span>
          </div>
          <p className="text-[11px] text-zinc-400 mt-1">
            Contract: <strong className="text-zinc-200">{metrics.contract_users}</strong> ta
          </p>
        </div>

        {/* Fair Queue Policy Info */}
        <div
          onClick={() => onNavigate('distribution')}
          className="bg-zinc-900/80 border border-zinc-800 hover:border-zinc-700 rounded-2xl p-4 cursor-pointer transition-all active:scale-[0.98]"
        >
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs font-medium">Taqsimot Nazorati</span>
            <ArrowUpRight className="w-4 h-4 text-zinc-400" />
          </div>
          <div className="text-sm font-semibold text-white">Fair Round-Robin</div>
          <p className="text-[11px] text-zinc-500 mt-1">0-post kanallarga ustuvorlik</p>
        </div>
      </div>

      {/* 4. Quick Actions */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        <button
          onClick={() => onNavigate('sources')}
          className="px-3 py-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 rounded-xl text-xs font-medium text-zinc-200 flex items-center gap-1.5 shrink-0 transition-colors"
        >
          <Rss className="w-3.5 h-3.5 text-emerald-400" />
          <span>Yangi Manba Qo‘shish</span>
        </button>
        <button
          onClick={() => onNavigate('posts')}
          className="px-3 py-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 rounded-xl text-xs font-medium text-zinc-200 flex items-center gap-1.5 shrink-0 transition-colors"
        >
          <Layers className="w-3.5 h-3.5 text-indigo-400" />
          <span>Post Poolni Ko‘rish</span>
        </button>
        <button
          onClick={() => onNavigate('channels')}
          className="px-3 py-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 rounded-xl text-xs font-medium text-zinc-200 flex items-center gap-1.5 shrink-0 transition-colors"
        >
          <Radio className="w-3.5 h-3.5 text-amber-400" />
          <span>Kanallarni Boshqarish</span>
        </button>
      </div>

      {/* 5. Recent Activity Feed */}
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-4 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Clock className="w-4 h-4 text-emerald-400" />
            <span>So‘nggi Yetkazilgan Xabarlar</span>
          </h3>
          <button
            onClick={() => onNavigate('distribution')}
            className="text-xs text-emerald-400 hover:text-emerald-300 font-medium flex items-center gap-1"
          >
            <span>Barchasi</span>
            <ArrowUpRight className="w-3 h-3" />
          </button>
        </div>

        {data?.recent_activity && data.recent_activity.length > 0 ? (
          <div className="divide-y divide-zinc-800/60">
            {data.recent_activity.map((item, idx) => (
              <div key={item.signature || idx} className="py-2.5 first:pt-0 last:pb-0 flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300">
                      {item.source_id.replace('src_', '')}
                    </span>
                    <span className="text-[11px] text-emerald-400 font-medium truncate">
                      {item.channel_title || `Kanal ${item.channel_id}`}
                    </span>
                  </div>
                  <h4 className="text-xs font-medium text-zinc-200 line-clamp-2 leading-relaxed">
                    {item.title}
                  </h4>
                </div>
                <div className="text-right shrink-0">
                  <span className="text-[10px] text-zinc-500 block mb-1">
                    {formatTimeAgo(item.delivered_at)}
                  </span>
                  {item.url && (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-zinc-400 hover:text-white inline-flex items-center"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-8 text-center text-zinc-500 text-xs">
            Hozircha yetkazilgan postlar jurnali bo‘sh.
          </div>
        )}
      </div>
    </div>
  );
};
