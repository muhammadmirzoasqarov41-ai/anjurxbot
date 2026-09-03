import React, { useState } from 'react';
import { AlertTriangle, ShieldAlert, CheckCircle2, RotateCcw, Filter, UserX } from 'lucide-react';
import { ModerationLog } from '../types';

interface ModerationViewProps {
  logs: ModerationLog[];
  onClearWarns: (userId: number) => Promise<void>;
}

export const ModerationView: React.FC<ModerationViewProps> = ({ logs, onClearWarns }) => {
  const [filterAction, setFilterAction] = useState<string>('all');
  const [targetUserId, setTargetUserId] = useState('');
  const [isClearing, setIsClearing] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  const filteredLogs = logs.filter((log) => {
    if (filterAction === 'all') return true;
    return log.action === filterAction;
  });

  const handleClear = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetUserId) return;
    setIsClearing(true);
    try {
      await onClearWarns(Number(targetUserId));
      setSuccessMessage(`Foydalanuvchi ${targetUserId} ogohlantirishlari olib tashlandi!`);
      setTargetUserId('');
      setTimeout(() => setSuccessMessage(''), 4000);
    } finally {
      setIsClearing(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-white tracking-tight">⚠️ Ogohlantirishlar & Moderatsiya</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
              Tarix & Jazolar
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Bot tomonidan qo'llanilgan avtomatik ogohlantirishlar va administrator harakatlari
          </p>
        </div>
      </div>

      {/* Manual Clear Warnings Wizard (bot /clearwarns equivalent) */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-2">
          <RotateCcw className="w-4 h-4 text-blue-400" />
          <h2 className="text-sm font-bold text-white">
            Ogohlantirishlarni Tozalash (/clearwarns)
          </h2>
        </div>
        <p className="text-xs text-slate-400 mb-3">
          Foydalanuvchining to'plangan 3 ta ogohlantirishini va cheklovini bekor qilish
        </p>

        <form onSubmit={handleClear} className="flex flex-col sm:flex-row gap-3">
          <input
            type="number"
            required
            placeholder="Telegram User ID (masalan: 729104882)..."
            value={targetUserId}
            onChange={(e) => setTargetUserId(e.target.value)}
            className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 font-mono"
          />
          <button
            type="submit"
            disabled={isClearing}
            className="px-5 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 shadow-sm"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>{isClearing ? 'Tozalanmoqda...' : 'Warnlarni tozalash'}</span>
          </button>
        </form>

        {successMessage && (
          <div className="mt-3 text-xs text-emerald-400 flex items-center gap-1.5 font-medium">
            <CheckCircle2 className="w-4 h-4" />
            <span>{successMessage}</span>
          </div>
        )}
      </div>

      {/* Filters Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-300">Filter:</span>
          <div className="flex gap-1">
            {[
              { id: 'all', label: 'Barchasi' },
              { id: 'warn', label: 'Warn' },
              { id: 'mute', label: 'Mute' },
              { id: 'ban', label: 'Ban' },
              { id: 'clear_warns', label: 'Tozalangan' },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setFilterAction(f.id)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                  filterAction === f.id
                    ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                    : 'text-slate-400 hover:text-white bg-slate-800/40'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Moderation Log Table */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-800/60 text-slate-300 text-xs font-semibold uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Vaqt</th>
                <th className="py-3 px-4">Guruh</th>
                <th className="py-3 px-4">Foydalanuvchi</th>
                <th className="py-3 px-4">Harakat</th>
                <th className="py-3 px-4">Sabab</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-400 text-sm">
                    Tanlangan filtr bo'yicha ma'lumot topilmadi.
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-4 text-xs font-mono text-slate-400 whitespace-nowrap">
                      {log.timestamp}
                    </td>
                    <td className="py-3 px-4 text-slate-200 font-medium">
                      {log.group_title}
                    </td>
                    <td className="py-3 px-4 text-slate-300">
                      <span className="font-mono text-xs text-slate-400">ID: {log.user_id}</span>
                      {log.username && (
                        <span className="text-blue-400 ml-1.5 font-sans text-xs">
                          (@{log.username})
                        </span>
                      )}
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
                    <td className="py-3 px-4 text-xs text-slate-300 max-w-md">
                      {log.reason}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
