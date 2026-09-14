import React, { useState, useEffect } from 'react';
import { LogEntry } from '../types';
import { api } from '../api';
import { Terminal, Search, RefreshCw, AlertCircle, Info, AlertTriangle } from 'lucide-react';

export const LogsView: React.FC = () => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [levelFilter, setLevelFilter] = useState('ALL');
  const [search, setSearch] = useState('');

  const loadLogs = async () => {
    setLoading(true);
    try {
      const res = await api.getLogs({ level: levelFilter, search });
      setLogs(res.logs || []);
    } catch (err) {
      console.error('Error loading logs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, [levelFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadLogs();
  };

  return (
    <div className="space-y-4 pb-20">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <Terminal className="w-5 h-5 text-emerald-400" />
            <span>Operatsion Jurnallar (Logs)</span>
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Tizim hodisalari, RSS so‘rovlari va xatolar arxivi
          </p>
        </div>

        <button
          onClick={loadLogs}
          disabled={loading}
          className="p-2 bg-zinc-900 border border-zinc-800 rounded-xl text-zinc-300 hover:text-white self-start sm:self-auto"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-2">
        <form onSubmit={handleSearchSubmit} className="relative flex-1">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Jurnal bo‘yicha qidiruv..."
            className="w-full pl-8 pr-3 py-2 bg-zinc-900 border border-zinc-800 rounded-xl text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500"
          />
          <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-2.5" />
        </form>

        <div className="flex gap-1 bg-zinc-900 p-1 border border-zinc-800 rounded-xl overflow-x-auto">
          {['ALL', 'INFO', 'WARNING', 'ERROR'].map((lvl) => (
            <button
              key={lvl}
              onClick={() => setLevelFilter(lvl)}
              className={`px-3 py-1 text-xs font-medium rounded-lg transition-colors shrink-0 ${
                levelFilter === lvl
                  ? 'bg-zinc-800 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {lvl}
            </button>
          ))}
        </div>
      </div>

      {/* Logs Container */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-3 font-mono text-xs overflow-x-auto max-h-[500px] overflow-y-auto space-y-1.5">
        {logs.length === 0 ? (
          <div className="py-8 text-center text-zinc-600">Jurnal yozuvlari topilmadi</div>
        ) : (
          logs.map((log, idx) => {
            const isError = log.level === 'ERROR' || log.level === 'CRITICAL';
            const isWarning = log.level === 'WARNING';

            return (
              <div
                key={idx}
                className={`p-2 rounded-lg border text-[11px] flex items-start gap-2 ${
                  isError
                    ? 'bg-red-950/20 border-red-900/40 text-red-300'
                    : isWarning
                    ? 'bg-amber-950/20 border-amber-900/40 text-amber-300'
                    : 'bg-zinc-900/50 border-zinc-800/60 text-zinc-300'
                }`}
              >
                <span className="text-zinc-500 shrink-0">
                  {new Date(log.timestamp).toLocaleTimeString('uz-UZ')}
                </span>

                <span
                  className={`px-1 rounded text-[10px] uppercase font-bold shrink-0 ${
                    isError
                      ? 'bg-red-500/20 text-red-400'
                      : isWarning
                      ? 'bg-amber-500/20 text-amber-400'
                      : 'bg-zinc-800 text-zinc-400'
                  }`}
                >
                  {log.level}
                </span>

                <span className="text-indigo-400 shrink-0">[{log.component}]</span>

                <span className="flex-1 break-all leading-relaxed">{log.message}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
