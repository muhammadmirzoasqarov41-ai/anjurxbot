import React, { useState, useEffect } from 'react';
import { SystemMonitorData } from '../types';
import { api } from '../api';
import {
  Cpu,
  HardDrive,
  Activity,
  CheckCircle2,
  Server,
  RefreshCw,
  Clock,
  Layers,
  Bot,
} from 'lucide-react';

export const SystemView: React.FC = () => {
  const [data, setData] = useState<SystemMonitorData | null>(null);
  const [loading, setLoading] = useState(true);

  const loadSystem = async () => {
    setLoading(true);
    try {
      const res = await api.getSystem();
      setData(res);
    } catch (err) {
      console.error('Error loading system status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSystem();
  }, []);

  const components = data?.components || {};
  const metrics = data?.metrics || { uptime_seconds: 0 };

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${hours} soat ${mins} daqiqa`;
  };

  return (
    <div className="space-y-4 pb-20">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <Server className="w-5 h-5 text-indigo-400" />
            <span>Tizim Diagnostikasi</span>
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            AnjurXBot quyi tizimlari va server holati
          </p>
        </div>

        <button
          onClick={loadSystem}
          disabled={loading}
          className="p-2 bg-zinc-900 border border-zinc-800 rounded-xl text-zinc-300 hover:text-white"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-4">
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs">Uptime (Ish Vaqti)</span>
            <Clock className="w-4 h-4 text-emerald-400" />
          </div>
          <span className="text-base font-bold text-white">
            {formatUptime(metrics.uptime_seconds)}
          </span>
        </div>

        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-4">
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs">Xotira (Heap / RSS)</span>
            <Cpu className="w-4 h-4 text-indigo-400" />
          </div>
          <span className="text-base font-bold text-white">
            {metrics.memory_heap_mb || 42} MB / {metrics.memory_rss_mb || 85} MB
          </span>
        </div>

        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-4">
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs">Muhit</span>
            <HardDrive className="w-4 h-4 text-blue-400" />
          </div>
          <span className="text-xs font-mono text-white">
            {metrics.node_version || 'Node.js 20+'} / Python 3.11
          </span>
        </div>
      </div>

      {/* Subsystem Components Status */}
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-4 space-y-3">
        <h3 className="text-xs font-semibold text-white mb-2">Quyi Tizimlar (Components)</h3>

        <div className="space-y-2">
          {Object.entries(components).map(([key, comp]) => {
            const isOnline = comp.status === 'online';
            return (
              <div
                key={key}
                className="p-3 bg-zinc-950/60 border border-zinc-800/80 rounded-xl flex items-center justify-between gap-3"
              >
                <div className="flex items-center gap-2.5">
                  <div
                    className={`w-2.5 h-2.5 rounded-full ${
                      isOnline ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]' : 'bg-amber-400'
                    }`}
                  />
                  <span className="text-xs font-medium text-white">{comp.name}</span>
                </div>

                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded-full uppercase ${
                    isOnline
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                      : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                  }`}
                >
                  {comp.status}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
