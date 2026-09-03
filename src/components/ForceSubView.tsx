import React, { useState } from 'react';
import { Radio, Plus, Trash2, ExternalLink, ShieldCheck, AlertCircle } from 'lucide-react';
import { TelegramGroup, ForceSubChannel } from '../types';

interface ForceSubViewProps {
  groups: TelegramGroup[];
  onAddChannel: (groupId: string, channel: Partial<ForceSubChannel>) => Promise<void>;
  onRemoveChannel: (groupId: string, channelId: string | number) => Promise<void>;
}

export const ForceSubView: React.FC<ForceSubViewProps> = ({
  groups,
  onAddChannel,
  onRemoveChannel,
}) => {
  const [selectedGroupId, setSelectedGroupId] = useState<string>(groups[0]?._id || '');
  const selectedGroup = groups.find((g) => g._id === selectedGroupId) || groups[0];

  const [channelId, setChannelId] = useState('');
  const [channelUsername, setChannelUsername] = useState('');
  const [channelTitle, setChannelTitle] = useState('');
  const [inviteLink, setInviteLink] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!channelId || !channelTitle || !selectedGroup) return;

    setIsSubmitting(true);
    try {
      await onAddChannel(selectedGroup._id, {
        channel_id: channelId,
        username: channelUsername.replace(/^@/, ''),
        title: channelTitle,
        invite_link: inviteLink || (channelUsername ? `https://t.me/${channelUsername.replace(/^@/, '')}` : ''),
      });
      setChannelId('');
      setChannelUsername('');
      setChannelTitle('');
      setInviteLink('');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-white tracking-tight">📢 Majburiy Obuna (Force Subscribe)</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
              FSub Gateway
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Guruh a'zolari xabar yozishi uchun majburiy a'zo bo'lishi talab qilinadigan kanallar
          </p>
        </div>

        {/* Group Selector */}
        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-slate-400">Guruh:</label>
          <select
            id="select-fsub-group"
            value={selectedGroupId}
            onChange={(e) => setSelectedGroupId(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded-xl px-3 py-2 focus:outline-none focus:border-blue-500 font-medium"
          >
            {groups.map((g) => (
              <option key={g._id} value={g._id}>
                {g.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Info Card */}
      <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4 flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
        <div className="text-xs text-slate-300">
          <p className="font-semibold text-white mb-0.5">Qanday ishlaydi?</p>
          Telegram Bot har bir foydalanuvchi guruhga xabar yuborganda uning ushbu kanallardagi a'zoligini tekshiradi (<code className="text-blue-300 font-mono">getChatMember</code> orqali). Agar foydalanuvchi obuna bo'lmagan bo'lsa, xabari o'chiriladi va unga obuna tugmalari ko'rsatiladi.
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Channels List */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5">
            <h2 className="text-base font-bold text-white mb-3">Ulangan Majburiy Kanallar</h2>

            {(!selectedGroup?.fsub_channels || selectedGroup.fsub_channels.length === 0) ? (
              <div className="text-center py-8 text-slate-400 text-sm bg-slate-800/30 rounded-xl border border-dashed border-slate-800">
                Ushbu guruhga hozircha majburiy kanallar qo'shilmagan.
              </div>
            ) : (
              <div className="space-y-3">
                {selectedGroup.fsub_channels.map((chan) => (
                  <div
                    key={String(chan.channel_id)}
                    className="bg-slate-800/50 border border-slate-700/60 rounded-xl p-4 flex items-center justify-between gap-4"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center">
                        <Radio className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-white text-sm">{chan.title}</span>
                          {chan.username && (
                            <span className="text-xs text-blue-400">@{chan.username}</span>
                          )}
                        </div>
                        <div className="text-xs text-slate-400 mt-0.5 flex items-center gap-3 font-mono">
                          <span>ID: {chan.channel_id}</span>
                          {chan.invite_link && (
                            <a
                              href={chan.invite_link}
                              target="_blank"
                              rel="noreferrer"
                              className="text-blue-400 hover:underline flex items-center gap-1 font-sans"
                            >
                              <span>Havola</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          )}
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={() => onRemoveChannel(selectedGroup._id, chan.channel_id)}
                      className="p-2 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
                      title="Kanalni o'chirish"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right 1 Col: Add New Channel Form */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5">
          <h2 className="text-base font-bold text-white mb-1">Kanal Qo'shish</h2>
          <p className="text-xs text-slate-400 mb-4">
            Bot kanal admini bo'lishi kerak
          </p>

          <form onSubmit={handleAdd} className="space-y-3.5">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Kanal ID *
              </label>
              <input
                type="text"
                required
                placeholder="Masalan: -1001829471920"
                value={channelId}
                onChange={(e) => setChannelId(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Kanal Nomi *
              </label>
              <input
                type="text"
                required
                placeholder="Masalan: Yangiliklar Kanali"
                value={channelTitle}
                onChange={(e) => setChannelTitle(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Username (@ ixtiyoriy)
              </label>
              <input
                type="text"
                placeholder="masalan: rasmiy_kanal"
                value={channelUsername}
                onChange={(e) => setChannelUsername(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Taklif Havolasi (Invite Link)
              </label>
              <input
                type="text"
                placeholder="https://t.me/..."
                value={inviteLink}
                onChange={(e) => setInviteLink(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full mt-2 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 shadow-md shadow-blue-500/20"
            >
              <Plus className="w-4 h-4" />
              <span>{isSubmitting ? 'Qo‘shilmoqda...' : 'Kanalni biriktirish'}</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
