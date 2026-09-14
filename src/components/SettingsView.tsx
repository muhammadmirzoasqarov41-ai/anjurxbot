import React, { useState, useEffect } from 'react';
import { SettingsConfig } from '../types';
import { api } from '../api';
import { Settings, Shield, Clock, HardDrive, CheckCircle2 } from 'lucide-react';

export const SettingsView: React.FC = () => {
  const [config, setConfig] = useState<SettingsConfig | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getSettings().then((res) => {
      setConfig(res.config);
      setLoading(false);
    });
  }, []);

  return (
    <div className="space-y-4 pb-20">
      <div>
        <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
          <Settings className="w-5 h-5 text-zinc-400" />
          <span>Tizim Parametrlari</span>
        </h2>
        <p className="text-xs text-zinc-400 mt-0.5">
          Bot arxitekturasi va global konfiguratsiya qiymatlari
        </p>
      </div>

      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-4 space-y-3">
        <h3 className="text-xs font-semibold text-white mb-2">Asosiy Sozlamalar</h3>

        <div className="divide-y divide-zinc-800 text-xs">
          <div className="py-2.5 flex justify-between items-center">
            <span className="text-zinc-400">Vaqt Mintaqasi (Timezone):</span>
            <span className="font-mono text-white">{config?.timezone || 'Asia/Tashkent (UTC+5)'}</span>
          </div>

          <div className="py-2.5 flex justify-between items-center">
            <span className="text-zinc-400">Super Admin Telegram ID:</span>
            <span className="font-mono text-emerald-400 font-bold">
              {config?.super_admin_id || 8157452043}
            </span>
          </div>

          <div className="py-2.5 flex justify-between items-center">
            <span className="text-zinc-400">Free Tarif Standart Limiti:</span>
            <span className="font-mono text-white">{config?.default_free_limit || 3} post / kun</span>
          </div>

          <div className="py-2.5 flex justify-between items-center">
            <span className="text-zinc-400">Post Saqlanish Muddati (Retention):</span>
            <span className="font-mono text-indigo-400 font-bold">
              {config?.retention_days || 5} kun
            </span>
          </div>

          <div className="py-2.5 flex justify-between items-center">
            <span className="text-zinc-400">RSS Fetcher Oralig‘i:</span>
            <span className="font-mono text-white">{config?.fetch_interval_sec || 45} soniya</span>
          </div>

          <div className="py-2.5 flex justify-between items-center">
            <span className="text-zinc-400">Taqsimot Oralig‘i:</span>
            <span className="font-mono text-white">{config?.distribution_interval_sec || 15} soniya</span>
          </div>

          <div className="py-2.5 flex justify-between items-center">
            <span className="text-zinc-400">Ma'lumotlar Saqlash Turi:</span>
            <span className="font-mono text-white">{config?.storage_type || 'Local JSON + Firestore'}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
