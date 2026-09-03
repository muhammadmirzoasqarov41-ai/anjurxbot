import React from 'react';
import { Shield, Users, Radio, AlertTriangle, CheckCircle, Flame, ExternalLink, Zap, Clock, Server } from 'lucide-react';
import { SystemStats, TelegramGroup, ModerationLog } from '../types';

interface DashboardViewProps {
  stats: SystemStats | null;
  groups: TelegramGroup[];
  recentLogs: ModerationLog[];
  onNavigate: (tab: string) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  stats,
  groups,
  recentLogs,
  onNavigate,
}) => {
  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-blue-900/40 via-slate-900 to-indigo-950/40 border border-blue-500/20 rounded-2xl p-6 relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20"></div>
        <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-400/30 mb-2">
              <Shield className="w-3.5 h-3.5" /> AnjurXBot 2026 versiya
            </span>
            <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Guruh Qorovuli & Boshqaruv Markazi
            </h1>
            <p className="text-slate-300 text-sm mt-1 max-w-2xl">
              Telegram guruhlaridagi spam, reklama, taqiqlangan havolalar va qallobliklarni avtomatlashtirilgan real-vaqt nazorati bilan himoya qiling.
            </p>
          </div>
          <div className="flex flex-wrap gap-2.5">
            <button
              id="btn-quick-simulator"
              onClick={() => onNavigate('simulator')}
              className="px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold rounded-xl transition-colors flex items-center gap-2 shadow-lg shadow-blue-600/20"
            >
              <Zap className="w-4 h-4" />
              <span>Xabar Sinovchi</span>
            </button>
            <button
              id="btn-quick-guard"
              onClick={() => onNavigate('guard')}
              className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold rounded-xl border border-slate-700 transition-colors flex items-center gap-2"
            >
              <Shield className="w-4 h-4" />
              <span>Qorovul Sozlamalari</span>
            </button>
          </div>
        </div>
      </div>

      {/* Metric Counters */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Foydalanuvchilar</span>
            <div className="w-9 h-9 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center">
              <Users className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-extrabold text-white tracking-tight">
              {stats?.total_users ?? 0}
            </span>
            <span className="text-xs text-emerald-400 font-medium ml-2">Bazadagi yozuvlar</span>
          </div>
          <p className="text-xs text-slate-400 mt-1">Guruh a'zolari va faol foydalanuvchilar</p>
        </div>

        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Faol Guruhlar</span>
            <div className="w-9 h-9 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
              <Shield className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-extrabold text-white tracking-tight">
              {stats?.active_guard_groups ?? 0} / {stats?.total_groups ?? 0}
            </span>
            <span className="text-xs text-emerald-400 font-medium ml-2">100% himoyada</span>
          </div>
          <p className="text-xs text-slate-400 mt-1">Qorovul faol bo'lgan guruhlar soni</p>
        </div>

        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Bloklangan Spam</span>
            <div className="w-9 h-9 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center">
              <Flame className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-extrabold text-white tracking-tight">
              {stats?.spam_blocked ?? 0}
            </span>
            <span className="text-xs text-amber-400 font-medium ml-2">ta xabar</span>
          </div>
          <p className="text-xs text-slate-400 mt-1">Anti-Spam va Anti-Ads filtrlari tomonidan</p>
        </div>

        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">O'chirilgan Linklar</span>
            <div className="w-9 h-9 rounded-lg bg-rose-500/10 text-rose-400 flex items-center justify-center">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-extrabold text-white tracking-tight">
              {stats?.links_deleted ?? 0}
            </span>
            <span className="text-xs text-rose-400 font-medium ml-2">ta havola</span>
          </div>
          <p className="text-xs text-slate-400 mt-1">Anti-Link himoyasi orqali tozalangan</p>
        </div>
      </div>

      {/* Two Column Layout: System Status & Monitored Groups */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Protected Groups */}
        <div className="lg:col-span-2 bg-slate-900/70 border border-slate-800 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-bold text-white">Himoyalangan Guruhlar</h2>
              <p className="text-xs text-slate-400">Telegram guruhlarining holati va sozlamalari</p>
            </div>
            <button
              id="btn-view-all-guard"
              onClick={() => onNavigate('guard')}
              className="text-xs text-blue-400 hover:text-blue-300 font-medium flex items-center gap-1"
            >
              <span>Barcha sozlamalar</span>
              <ExternalLink className="w-3 h-3" />
            </button>
          </div>

          <div className="space-y-3">
            {groups.map((group) => (
              <div
                key={group._id}
                className="bg-slate-800/40 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:border-slate-700 transition-colors"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-white text-base">{group.title}</span>
                    {group.guard.enabled ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        Faol
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-slate-700 text-slate-400">
                        O'chirilgan
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1 text-xs text-slate-400">
                    <span>ID: {group.group_id}</span>
                    {group.username && <span>@{group.username}</span>}
                    <span>{group.members_count.toLocaleString()} ta a'zo</span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <div className="flex flex-wrap gap-1 text-[11px]">
                    {group.guard.anti_spam && (
                      <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-400">Spam</span>
                    )}
                    {group.guard.anti_flood && (
                      <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-400">Flood</span>
                    )}
                    {group.guard.anti_link && (
                      <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-400">Link</span>
                    )}
                    {group.guard.bad_words && (
                      <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400">So'zlar</span>
                    )}
                  </div>

                  <button
                    onClick={() => onNavigate('guard')}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300 transition-colors"
                  >
                    Sozlash
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right 1 Col: System Engine Diagnostics */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-6 flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Server className="w-5 h-5 text-blue-400" />
              <h2 className="text-lg font-bold text-white">Tizim Diagnostikasi</h2>
            </div>

            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between py-2 border-b border-slate-800">
                <span className="text-slate-400">Salomatlik (Health):</span>
                <span className="flex items-center gap-1.5 text-emerald-400 font-semibold text-xs bg-emerald-500/10 px-2 py-0.5 rounded">
                  <CheckCircle className="w-3.5 h-3.5" /> status: ok
                </span>
              </div>

              <div className="flex items-center justify-between py-2 border-b border-slate-800">
                <span className="text-slate-400">Web Port:</span>
                <span className="text-slate-200 font-mono text-xs">3000 (0.0.0.0)</span>
              </div>

              <div className="flex items-center justify-between py-2 border-b border-slate-800">
                <span className="text-slate-400">Ma'lumotlar ombori:</span>
                <span className="text-blue-400 font-semibold text-xs">
                  {stats ? 'In-Memory / Firestore tayyor' : 'Yuklanmoqda...'}
                </span>
              </div>

              <div className="flex items-center justify-between py-2 border-b border-slate-800">
                <span className="text-slate-400">Ish vaqti (Uptime):</span>
                <span className="text-slate-200 font-mono text-xs flex items-center gap-1">
                  <Clock className="w-3 h-3 text-slate-400" />
                  {stats?.uptime_seconds ? `${Math.floor(stats.uptime_seconds / 60)} daqiqa` : '1 daqiqa'}
                </span>
              </div>

              <div className="flex items-center justify-between py-2">
                <span className="text-slate-400">Admin kalit himoyasi:</span>
                <span className="text-emerald-400 text-xs font-medium">HMAC-SHA256 faol</span>
              </div>
            </div>
          </div>

          <div className="bg-slate-800/40 rounded-xl p-3 border border-slate-800 text-xs text-slate-400">
            <span className="font-semibold text-slate-300 block mb-1">ℹ️ Xavfsizlik eslatmasi</span>
            Telegram bot tokeni va maxfiy kalitlar faqatgina server muhitida (environment variables) saqlanadi va brauzerga chiqarilmaydi.
          </div>
        </div>
      </div>

      {/* Recent Moderation Log */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold text-white">So'nggi Moderatsiya Harakatlari</h2>
            <p className="text-xs text-slate-400">Qorovul tomonidan avtomatik qo'llanilgan jazolar va ogohlantirishlar</p>
          </div>
          <button
            id="btn-view-all-logs"
            onClick={() => onNavigate('moderation')}
            className="text-xs text-blue-400 hover:text-blue-300 font-medium flex items-center gap-1"
          >
            <span>Barchasini ko'rish</span>
            <ExternalLink className="w-3 h-3" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-800/50 text-slate-400 text-xs uppercase tracking-wider">
              <tr>
                <th className="py-3 px-4 rounded-l-lg">Vaqt</th>
                <th className="py-3 px-4">Guruh</th>
                <th className="py-3 px-4">Foydalanuvchi</th>
                <th className="py-3 px-4">Harakat</th>
                <th className="py-3 px-4 rounded-r-lg">Sabab</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {recentLogs.slice(0, 5).map((log) => (
                <tr key={log.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-3 px-4 text-xs font-mono text-slate-400">{log.timestamp}</td>
                  <td className="py-3 px-4 text-slate-200 font-medium">{log.group_title}</td>
                  <td className="py-3 px-4 text-slate-300">
                    <span className="font-mono text-xs text-slate-400">ID: {log.user_id}</span>
                    {log.username && <span className="text-blue-400 ml-1.5">(@{log.username})</span>}
                  </td>
                  <td className="py-3 px-4">
                    {log.action === 'ban' && (
                      <span className="px-2 py-0.5 rounded text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                        Ban
                      </span>
                    )}
                    {log.action === 'mute' && (
                      <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                        Mute
                      </span>
                    )}
                    {log.action === 'warn' && (
                      <span className="px-2 py-0.5 rounded text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                        Warn
                      </span>
                    )}
                    {log.action === 'clear_warns' && (
                      <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        Tozalandi
                      </span>
                    )}
                    {log.action === 'delete' && (
                      <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-700 text-slate-300">
                        O'chirildi
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-xs text-slate-300 max-w-md truncate">{log.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
