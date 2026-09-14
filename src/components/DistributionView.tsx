import React, { useState, useEffect } from 'react';
import { DistributionData } from '../types';
import { api } from '../api';
import {
  Send,
  Radio,
  Clock,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  Loader2,
  RefreshCw,
} from 'lucide-react';

interface DistributionViewProps {
  onRefresh: () => void;
}

export const DistributionView: React.FC<DistributionViewProps> = ({ onRefresh }) => {
  const [data, setData] = useState<DistributionData | null>(null);
  const [loading, setLoading] = useState(true);

  const loadDistribution = async () => {
    setLoading(true);
    try {
      const res = await api.getDistribution();
      setData(res);
    } catch (err: any) {
      console.error('Error loading distribution:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDistribution();
  }, []);

  if (loading && !data) {
    return (
      <div className="py-20 text-center text-zinc-500 flex flex-col items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-emerald-500 mb-2" />
        <span className="text-xs">Taqsimot ma'lumotlari yuklanmoqda...</span>
      </div>
    );
  }

  return (
    <div className="space-y-5 pb-20">
      {/* Header */}
      <div>
        <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
          <Send className="w-5 h-5 text-emerald-400" />
          <span>Taqsimot va Yetkazish Nazorati</span>
        </h2>
        <p className="text-xs text-zinc-400 mt-0.5">
          Fair Queue algoritmi asosida barcha kanallarga adolatli yangilik yetkazish
        </p>
      </div>

      {/* Engine Status Card */}
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span className="text-xs font-semibold text-white">Adolatli Taqsimot Qoidasi</span>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-medium">
            {data?.fair_queue_policy || 'Fair Distribution'}
          </span>
        </div>
        <p className="text-xs text-zinc-300 leading-relaxed">
          Ushbu algoritm bir kanal barcha yangiliklarni monopol qilib olmasligini kafolatlaydi.
          Bugun hali post olmagan (0 ta) kanallar birinchi navbatda xizmat ko‘rsatiladi.
          Har bir post kanallarga faqat bir marta yuboriladi va takrorlanishdan to‘liq himoyalangan.
        </p>
      </div>

      {/* Channels Status Today */}
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-4">
        <h3 className="text-xs font-semibold text-white mb-3 flex items-center gap-2">
          <Radio className="w-4 h-4 text-emerald-400" />
          <span>Bugungi Kanallar Holati ({data?.channels_summary?.length || 0})</span>
        </h3>

        <div className="space-y-2">
          {data?.channels_summary && data.channels_summary.length > 0 ? (
            data.channels_summary.map((ch) => {
              const reachedLimit = ch.today_delivered >= ch.daily_limit;
              const percent = Math.min(100, Math.round((ch.today_delivered / ch.daily_limit) * 100));

              return (
                <div
                  key={ch.chat_id}
                  className="p-3 bg-zinc-950/60 border border-zinc-800/80 rounded-xl"
                >
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-xs font-medium text-white truncate">{ch.title}</span>
                      <span
                        className={`text-[9px] uppercase px-1 py-0.2 rounded border ${
                          ch.plan === 'contract'
                            ? 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30'
                            : 'bg-zinc-800 text-zinc-400 border-zinc-700'
                        }`}
                      >
                        {ch.plan}
                      </span>
                    </div>

                    <span
                      className={`text-[11px] font-mono font-bold ${
                        reachedLimit ? 'text-amber-400' : 'text-emerald-400'
                      }`}
                    >
                      {ch.today_delivered} / {ch.daily_limit} post
                    </span>
                  </div>

                  {/* Progress Bar */}
                  <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden mb-2">
                    <div
                      className={`h-full transition-all duration-300 ${
                        reachedLimit ? 'bg-amber-400' : 'bg-emerald-500'
                      }`}
                      style={{ width: `${percent}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-[10px] text-zinc-500 font-mono">
                    <span>Rejim: {ch.schedule_mode}</span>
                    <span>
                      {reachedLimit ? 'Kunlik limitga yetdi' : 'Yangi postlarni qabul qilishga tayyor'}
                    </span>
                  </div>
                </div>
              );
            })
          ) : (
            <p className="text-xs text-zinc-500">Ulangan kanallar mavjud emas</p>
          )}
        </div>
      </div>

      {/* Recent Deliveries List */}
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-4">
        <h3 className="text-xs font-semibold text-white mb-3 flex items-center gap-2">
          <Clock className="w-4 h-4 text-emerald-400" />
          <span>So‘nggi Yetkazilgan Xabarlar Jurnali</span>
        </h3>

        {data?.recent_deliveries && data.recent_deliveries.length > 0 ? (
          <div className="divide-y divide-zinc-800/80">
            {data.recent_deliveries.map((item, idx) => (
              <div key={item.signature || idx} className="py-2.5 first:pt-0 last:pb-0">
                <div className="flex items-center justify-between gap-2 text-[10px] text-zinc-400 mb-1">
                  <span className="font-semibold text-emerald-400">
                    {item.channel_title || item.channel_id}
                  </span>
                  <span>{new Date(item.delivered_at).toLocaleTimeString('uz-UZ')}</span>
                </div>
                <h4 className="text-xs text-zinc-200 font-medium line-clamp-2">
                  {item.title}
                </h4>
                <div className="flex items-center justify-between mt-1 text-[10px] text-zinc-500 font-mono">
                  <span>Manba: {item.source_id.replace('src_', '')}</span>
                  {item.url && (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-zinc-400 hover:text-white flex items-center gap-1"
                    >
                      <span>Link</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-zinc-500">Yetkazilgan xabarlar tarixi bo‘sh</p>
        )}
      </div>
    </div>
  );
};
