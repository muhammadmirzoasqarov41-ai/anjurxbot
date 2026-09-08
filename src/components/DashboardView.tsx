import React from 'react';
import { Shield, Users, Radio, AlertTriangle, Zap, Clock, Terminal, Activity, CheckCircle2, ChevronRight, RefreshCw } from 'lucide-react';
import { SystemStats, TelegramGroup, ModerationLog } from '../types';

interface DashboardViewProps {
  stats: SystemStats | null;
  groups: TelegramGroup[];
  recentLogs: ModerationLog[];
  onNavigate: (tab: string) => void;
  onRefresh?: () => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  stats,
  groups,
  recentLogs,
  onNavigate,
  onRefresh,
}) => {
  return (
    <div className="space-y-6 font-mono-cyber">
      {/* Cybersecurity Telemetry Banner */}
      <div className="bg-[#080c14] border border-[#152233] rounded-xl p-6 relative overflow-hidden shadow-[0_10px_30px_rgba(0,0,0,0.8)]">
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-[#00ff66] to-transparent" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-5">
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-[#00ff66]/10 text-[#00ff66] border border-[#00ff66]/30">
                <span className="w-1.5 h-1.5 rounded-full bg-[#00ff66] animate-pulse" />
                PROTOCOL V2.4 PRODUCTION
              </span>
              <span className="text-xs text-slate-500">
                CLOUD RUN & RENDER UNIFIED ENGINE
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight flex items-center gap-2">
              <span>CYBER COMMAND & DEFENSE CENTER</span>
            </h1>
            <p className="text-slate-400 text-xs mt-1.5 max-w-2xl leading-relaxed">
              Real-time Telegram group protection against flood attacks, spam, unauthorized invite links, and malicious exploits.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {onRefresh && (
              <button
                onClick={onRefresh}
                className="p-2.5 bg-[#0d1522] hover:bg-[#142136] text-slate-300 hover:text-white rounded-lg border border-[#1b2b40] transition-colors cursor-pointer"
                title="Telemetry yangilash"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            )}
            <button
              id="btn-quick-simulator"
              onClick={() => onNavigate('simulator')}
              className="px-4 py-2.5 bg-[#00ff66] hover:bg-[#33ff85] text-black text-xs font-bold uppercase tracking-wider rounded-lg transition-all shadow-[0_0_15px_rgba(0,255,102,0.25)] flex items-center gap-2 cursor-pointer"
            >
              <Zap className="w-4 h-4" />
              <span>Xabar Sinovchi</span>
            </button>
            <button
              id="btn-quick-guard"
              onClick={() => onNavigate('guard')}
              className="px-4 py-2.5 bg-[#0d1522] hover:bg-[#152338] text-slate-200 text-xs font-semibold rounded-lg border border-[#1b2b40] transition-colors flex items-center gap-2 cursor-pointer"
            >
              <Shield className="w-4 h-4 text-[#00ff66]" />
              <span>Qorovul Sozlamalari</span>
            </button>
          </div>
        </div>

        {/* Real telemetry strip */}
        <div className="mt-5 pt-4 border-t border-[#141f30] grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="flex items-center gap-2 text-slate-400">
            <Clock className="w-3.5 h-3.5 text-[#00ff66]" />
            <span>Uptime: <strong className="text-white font-mono">{stats?.uptime_seconds ?? 0}s</strong></span>
          </div>
          <div className="flex items-center gap-2 text-slate-400">
            <Activity className="w-3.5 h-3.5 text-[#00ff66]" />
            <span>Firestore: <strong className="text-white">Active (anjurxbot)</strong></span>
          </div>
          <div className="flex items-center gap-2 text-slate-400">
            <Terminal className="w-3.5 h-3.5 text-[#00ff66]" />
            <span>Super Admin: <strong className="text-[#00ff66]">@usafes</strong></span>
          </div>
          <div className="flex items-center gap-2 text-slate-400">
            <Radio className="w-3.5 h-3.5 text-[#00ff66]" />
            <span>ID: <strong className="text-white font-mono">8157452043</strong></span>
          </div>
        </div>
      </div>

      {/* Metric Counters */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Users */}
        <div className="bg-[#080c14] border border-[#152233] rounded-xl p-5 hover:border-[#00ff66]/50 transition-all shadow-[0_5px_15px_rgba(0,0,0,0.5)]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Foydalanuvchilar
            </span>
            <div className="w-8 h-8 rounded-lg bg-[#0d1624] border border-[#1b2b40] text-[#00ff66] flex items-center justify-center">
              <Users className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white tracking-tight font-mono">
              {stats?.total_users ?? 0}
            </span>
            <span className="text-[11px] text-[#00ff66] font-medium">Bazadagi yozuvlar</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Guruh a'zolari va foydalanuvchilar</p>
        </div>

        {/* Active Groups */}
        <div className="bg-[#080c14] border border-[#152233] rounded-xl p-5 hover:border-[#00ff66]/50 transition-all shadow-[0_5px_15px_rgba(0,0,0,0.5)]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Faol Guruhlar
            </span>
            <div className="w-8 h-8 rounded-lg bg-[#0d1624] border border-[#1b2b40] text-[#00ff66] flex items-center justify-center">
              <Shield className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white tracking-tight font-mono">
              {stats?.active_guard_groups ?? groups.length} / {stats?.total_groups ?? groups.length}
            </span>
            <span className="text-[11px] text-[#00ff66] font-medium">Himoyalangan</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Qorovul nazoratidagi guruhlar</p>
        </div>

        {/* Spam & Threat Incidents */}
        <div className="bg-[#080c14] border border-[#152233] rounded-xl p-5 hover:border-[#00ff66]/50 transition-all shadow-[0_5px_15px_rgba(0,0,0,0.5)]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Bloklangan Spam
            </span>
            <div className="w-8 h-8 rounded-lg bg-[#0d1624] border border-[#1b2b40] text-amber-400 flex items-center justify-center">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white tracking-tight font-mono">
              {stats?.spam_blocked ?? 0}
            </span>
            <span className="text-[11px] text-amber-400 font-medium">Avtomatik</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Spam, reklama va flood filtrlandi</p>
        </div>

        {/* Deleted Links */}
        <div className="bg-[#080c14] border border-[#152233] rounded-xl p-5 hover:border-[#00ff66]/50 transition-all shadow-[0_5px_15px_rgba(0,0,0,0.5)]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              O'chirilgan Havolalar
            </span>
            <div className="w-8 h-8 rounded-lg bg-[#0d1624] border border-[#1b2b40] text-[#00ff66] flex items-center justify-center">
              <Zap className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white tracking-tight font-mono">
              {stats?.links_deleted ?? 0}
            </span>
            <span className="text-[11px] text-[#00ff66] font-medium">Anti-link</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Guruhda ruxsatsiz linklar</p>
        </div>
      </div>

      {/* Main Grid: Groups Overview + Live Security Logs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Groups Monitored (2 cols) */}
        <div className="lg:col-span-2 bg-[#080c14] border border-[#152233] rounded-xl p-5 shadow-[0_5px_15px_rgba(0,0,0,0.5)]">
          <div className="flex items-center justify-between pb-3 border-b border-[#141f30] mb-4">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-[#00ff66]" />
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                Ulangan Guruhlar Ro'yxati
              </h2>
            </div>
            <button
              onClick={() => onNavigate('guard')}
              className="text-xs text-[#00ff66] hover:underline flex items-center gap-1 cursor-pointer"
            >
              <span>Barchasi</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {groups.length === 0 ? (
            <div className="text-center py-10 text-slate-500 text-xs">
              <Shield className="w-8 h-8 mx-auto mb-2 text-slate-600 opacity-40" />
              <p>Hozircha guruhlar ro'yxatga olinmagan.</p>
              <p className="text-[11px] text-slate-600 mt-1">
                Botni Telegram guruhga qo'shing va admin huquqini bering.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[#141f30] text-slate-400 text-[11px]">
                    <th className="pb-2 font-medium">Guruh Nomi</th>
                    <th className="pb-2 font-medium">Guruh ID</th>
                    <th className="pb-2 font-medium">A'zolar</th>
                    <th className="pb-2 font-medium">Qorovul</th>
                    <th className="pb-2 font-medium text-right">Amal</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#121c2b]">
                  {groups.slice(0, 5).map((group) => (
                    <tr key={group._id} className="hover:bg-[#0c1320] transition-colors">
                      <td className="py-3 font-semibold text-white">
                        {group.title || 'Nomsiz Guruh'}
                      </td>
                      <td className="py-3 font-mono text-slate-400">
                        {group.group_id}
                      </td>
                      <td className="py-3 text-slate-300">
                        {group.members_count || 0}
                      </td>
                      <td className="py-3">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-[#00ff66]/10 text-[#00ff66] border border-[#00ff66]/30">
                          <CheckCircle2 className="w-3 h-3" /> Faol
                        </span>
                      </td>
                      <td className="py-3 text-right">
                        <button
                          onClick={() => onNavigate('guard')}
                          className="text-[#00ff66] hover:text-[#33ff85] font-semibold text-[11px] cursor-pointer"
                        >
                          Sozlash
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Real Moderation Incident Feed (1 col) */}
        <div className="bg-[#080c14] border border-[#152233] rounded-xl p-5 shadow-[0_5px_15px_rgba(0,0,0,0.5)]">
          <div className="flex items-center justify-between pb-3 border-b border-[#141f30] mb-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                Xavfsizlik Jurnali
              </h2>
            </div>
            <button
              onClick={() => onNavigate('moderation')}
              className="text-xs text-[#00ff66] hover:underline flex items-center gap-1 cursor-pointer"
            >
              <span>Jurnal</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {recentLogs.length === 0 ? (
            <div className="text-center py-10 text-slate-500 text-xs">
              <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-[#00ff66] opacity-30" />
              <p>Xavfsizlik hodisalari yo'q.</p>
              <p className="text-[11px] text-slate-600 mt-1">Barcha guruhlar toza va tinch.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {recentLogs.slice(0, 5).map((log) => (
                <div
                  key={log.id}
                  className="p-3 bg-[#0a101a] border border-[#141f30] rounded-lg text-xs"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-white">
                      {log.username ? `@${log.username}` : `ID: ${log.user_id}`}
                    </span>
                    <span className="text-[10px] text-slate-500">
                      {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : 'Yaqinda'}
                    </span>
                  </div>
                  <div className="text-slate-400 text-[11px]">
                    Sabab: <span className="text-amber-300 font-mono">{log.reason}</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-1">
                    Guruh: {log.group_title || log.group_id} &bull; Amal: {log.action}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
