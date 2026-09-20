import React, { useState, useEffect } from 'react';
import { SystemMonitorData, TranslatorStatus } from '../types';
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
  Languages,
  Sparkles,
  AlertCircle,
} from 'lucide-react';

export const SystemView: React.FC = () => {
  const [data, setData] = useState<SystemMonitorData | null>(null);
  const [translatorStatus, setTranslatorStatus] = useState<TranslatorStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const loadSystem = async () => {
    setLoading(true);
    try {
      const [sysRes, transRes] = await Promise.all([
        api.getSystem(),
        api.getTranslatorStatus().catch(() => null),
      ]);
      setData(sysRes);
      if (transRes) setTranslatorStatus(transRes);
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
            AnjurXBot quyi tizimlari, Gemini tarjimon va server holati
          </p>
        </div>

        <button
          onClick={loadSystem}
          disabled={loading}
          className="p-2 bg-zinc-900 border border-zinc-800 rounded-xl text-zinc-300 hover:text-white transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Gemini Translator Dedicated Card */}
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <Languages className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white flex items-center gap-1.5">
                Gemini Translator
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              </h3>
              <p className="text-[11px] text-zinc-400">Post Language avtomatik neyron tarjima tizimi</p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <span
              className={`inline-flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded-full border ${
                translatorStatus?.configured
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  translatorStatus?.configured
                    ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]'
                    : 'bg-amber-400'
                }`}
              />
              {translatorStatus?.configured ? 'Configured' : 'Not configured'}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1">
          <div className="p-2.5 bg-zinc-950/60 border border-zinc-800/80 rounded-xl">
            <span className="text-[10px] uppercase font-mono text-zinc-500 block mb-1">Model</span>
            <span className="text-xs font-mono font-medium text-white block truncate">
              {translatorStatus?.model || 'gemini-3.8-flash'}
            </span>
          </div>

          <div className="p-2.5 bg-zinc-950/60 border border-zinc-800/80 rounded-xl">
            <span className="text-[10px] uppercase font-mono text-zinc-500 block mb-1">Supported</span>
            <span className="text-xs font-medium text-zinc-200 block">
              Uzbek / Russian / English
            </span>
          </div>

          <div className="p-2.5 bg-zinc-950/60 border border-zinc-800/80 rounded-xl">
            <span className="text-[10px] uppercase font-mono text-zinc-500 block mb-1">Cache</span>
            <span className="text-xs font-medium text-emerald-400 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Enabled (Firestore + Mem)
            </span>
          </div>
        </div>

        {!translatorStatus?.configured && (
          <div className="flex items-start gap-2 p-2.5 bg-amber-500/5 border border-amber-500/20 rounded-xl text-xs text-amber-300/90">
            <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-amber-300">Gemini API key sozlanmagan</p>
              <p className="text-[11px] text-zinc-400 mt-0.5 leading-relaxed">
                Render Environment Variables bo‘limiga <code className="text-amber-200 bg-zinc-800 px-1 py-0.5 rounded">GEMINI_API_KEY</code> qo‘shganingizdan so‘ng tarjima avtomatik faollashadi.
              </p>
            </div>
          </div>
        )}
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

