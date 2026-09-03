import React, { useState } from 'react';
import { PlayCircle, Send, CheckCircle2, AlertTriangle, ShieldX, Sparkles, MessageSquare } from 'lucide-react';
import { TelegramGroup } from '../types';

interface SimulatorViewProps {
  groups: TelegramGroup[];
  onSimulateMessage: (groupId: number, text: string, username: string) => Promise<any>;
}

export const SimulatorView: React.FC<SimulatorViewProps> = ({ groups, onSimulateMessage }) => {
  const [selectedGroupId, setSelectedGroupId] = useState<number>(groups[0]?.group_id || -1001928472910);
  const [testUsername, setTestUsername] = useState('test_user');
  const [messageText, setMessageText] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [history, setHistory] = useState<
    Array<{
      id: string;
      user: string;
      text: string;
      result: {
        allowed: boolean;
        action: string;
        reason: string;
      };
      time: string;
    }>
  >([]);

  const presets = [
    { label: "✅ Toza xabar", text: "Salom dasturchilar! Hammaga xayrli kun." },
    { label: "🔗 Havola (Link)", text: "Dasturchilar kanaliga qo'shiling: https://t.me/yangi_kanal_2026" },
    { label: "🎰 Reklama / Stavka", text: "1xbet stavkalar orqali kuniga 500$ daromad oling! Kazino bonusi." },
    { label: "🤬 Taqiqlangan so'z", text: "Bu guruhdagi hamma ahmoq ekan, hech kim yordam bermadi." },
  ];

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend ?? messageText).trim();
    if (!text) return;

    setIsProcessing(true);
    try {
      const res = await onSimulateMessage(selectedGroupId, text, testUsername);
      setHistory((prev) => [
        {
          id: String(Date.now()),
          user: testUsername,
          text,
          result: res,
          time: new Date().toLocaleTimeString(),
        },
        ...prev,
      ]);
      if (!textToSend) setMessageText('');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-white tracking-tight">🧪 Xabar Sinovchi (Guard Simulator)</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
              Interaktiv Test
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Bot xabar filtrlari (Anti-Link, Anti-Spam, Bad Words, Ads) qanday ishlashini to'g'ridan-to'g'ri sinab ko'ring
          </p>
        </div>

        {/* Group Selector */}
        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-slate-400">Sinov guruhi:</label>
          <select
            id="select-sim-group"
            value={selectedGroupId}
            onChange={(e) => setSelectedGroupId(Number(e.target.value))}
            className="bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded-xl px-3 py-2 focus:outline-none focus:border-blue-500 font-medium"
          >
            {groups.map((g) => (
              <option key={g._id} value={g.group_id}>
                {g.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Preset Buttons */}
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs font-semibold text-slate-400 mr-1 flex items-center gap-1">
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          Tezkor namunalar:
        </span>
        {presets.map((p, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => handleSend(p.text)}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 rounded-lg border border-slate-700 transition-colors"
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Input Box */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5">
        <div className="flex items-center gap-3 mb-3">
          <div className="flex-1 max-w-xs">
            <label className="block text-xs font-semibold text-slate-400 mb-1">Foydalanuvchi nomi</label>
            <input
              type="text"
              value={testUsername}
              onChange={(e) => setTestUsername(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
            />
          </div>
        </div>

        <div className="flex gap-2">
          <input
            id="input-sim-message"
            type="text"
            placeholder="Telegram guruhiga yuboriladigan xabar matnini kiriting..."
            value={messageText}
            onChange={(e) => setMessageText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSend();
            }}
            className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
          <button
            id="btn-sim-send"
            onClick={() => handleSend()}
            disabled={isProcessing || !messageText.trim()}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-sm font-semibold transition-colors flex items-center gap-2 shadow-lg shadow-blue-500/20"
          >
            <Send className="w-4 h-4" />
            <span>{isProcessing ? 'Tekshirilmoqda...' : 'Sinash'}</span>
          </button>
        </div>
      </div>

      {/* Live Simulation Stream */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <MessageSquare className="w-4 h-4 text-blue-400" />
          <h2 className="text-base font-bold text-white">Tekshiruv Natijalari Jurnali</h2>
        </div>

        {history.length === 0 ? (
          <div className="text-center py-10 text-slate-500 text-sm">
            Yuqoridagi namunani bosing yoki o'z xabaringizni yozib Qorovul himoyasini sinab ko'ring.
          </div>
        ) : (
          <div className="space-y-3">
            {history.map((item) => (
              <div
                key={item.id}
                className={`p-4 rounded-xl border transition-all ${
                  item.result.allowed
                    ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-300'
                    : 'bg-rose-950/20 border-rose-500/30 text-rose-300'
                }`}
              >
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-white">@{item.user}</span>
                    <span className="text-slate-400 font-mono text-[11px]">{item.time}</span>
                  </div>
                  <div>
                    {item.result.allowed ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                        <CheckCircle2 className="w-3 h-3" /> Ruxsat berildi
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30">
                        <ShieldX className="w-3 h-3" /> {item.result.action.toUpperCase()}
                      </span>
                    )}
                  </div>
                </div>

                <p className="text-sm font-medium text-slate-100 bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/80 mb-2">
                  "{item.text}"
                </p>

                <div className="text-xs flex items-center gap-1.5">
                  <span className="font-semibold text-slate-400">Qorovul xulosasi:</span>
                  <span className={item.result.allowed ? 'text-emerald-400 font-medium' : 'text-rose-400 font-medium'}>
                    {item.result.reason}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
