import React, { useState } from 'react';
import {
  Rss,
  Plus,
  Trash2,
  RefreshCw,
  ExternalLink,
  Upload,
  CheckCircle2,
  AlertTriangle,
  Copy,
  Clock,
  Send,
} from 'lucide-react';
import { RSSFeed, RSSStats } from '../types';

interface FeedsViewProps {
  feeds: RSSFeed[];
  stats: RSSStats | null;
  onAddFeed: (url: string, title: string) => Promise<boolean>;
  onDeleteFeed: (feedId: string) => Promise<void>;
  onSyncFeed: (feedId: string) => Promise<void>;
  onImportOpml: (file: File) => Promise<void>;
  loading: boolean;
}

export const FeedsView: React.FC<FeedsViewProps> = ({
  feeds,
  stats,
  onAddFeed,
  onDeleteFeed,
  onSyncFeed,
  onImportOpml,
  loading,
}) => {
  const [newUrl, setNewUrl] = useState('');
  const [newTitle, setNewTitle] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [actionFeedId, setActionFeedId] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUrl.trim()) return;

    setSubmitting(true);
    setStatusMessage(null);
    try {
      const ok = await onAddFeed(newUrl.trim(), newTitle.trim());
      if (ok) {
        setStatusMessage({ type: 'success', text: 'Yangi RSS lenta muvaffaqiyatli qo‘shildi!' });
        setNewUrl('');
        setNewTitle('');
      } else {
        setStatusMessage({ type: 'error', text: 'Feedni yuklab bo‘lmadi. Havolani tekshiring.' });
      }
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err.message || 'Xatolik yuz berdi' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleSync = async (feedId: string) => {
    setActionFeedId(feedId);
    try {
      await onSyncFeed(feedId);
      setStatusMessage({ type: 'success', text: 'Feed tekshirildi va sinxronizatsiya qilindi.' });
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: 'Sinxronizatsiyada xatolik' });
    } finally {
      setActionFeedId(null);
    }
  };

  const handleDelete = async (feedId: string, title: string) => {
    if (!confirm(`"${title}" lentasini va uning barcha obunalarini o‘chirmoqchimisiz?`)) {
      return;
    }
    setActionFeedId(feedId);
    try {
      await onDeleteFeed(feedId);
      setStatusMessage({ type: 'success', text: 'Feed muvaffaqiyatli o‘chirildi.' });
    } finally {
      setActionFeedId(null);
    }
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onImportOpml(file);
      e.target.value = '';
    }
  };

  return (
    <div className="space-y-6">
      {/* Overview Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5 relative overflow-hidden">
          <div className="flex items-center justify-between text-zinc-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Jami Lentalar</span>
            <div className="w-8 h-8 rounded-lg bg-orange-500/10 border border-orange-500/20 flex items-center justify-center text-orange-400">
              <Rss className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-extrabold text-white font-mono">{stats?.total_feeds ?? feeds.length}</span>
            <span className="text-xs text-zinc-500 ml-2">ta manba</span>
          </div>
          <div className="mt-2 flex items-center text-[11px] text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
            <span>Avtomatik tekshiruv faol</span>
          </div>
        </div>

        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5 relative overflow-hidden">
          <div className="flex items-center justify-between text-zinc-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Faol Obunalar</span>
            <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
              <Send className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-extrabold text-white font-mono">{stats?.active_subscriptions ?? 1}</span>
            <span className="text-xs text-zinc-500 ml-2">chat obunalari</span>
          </div>
          <div className="mt-2 flex items-center text-[11px] text-zinc-400">
            <span>Guruh, kanal va shaxsiy chatlar</span>
          </div>
        </div>

        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5 relative overflow-hidden">
          <div className="flex items-center justify-between text-zinc-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Yetkazilgan Postlar</span>
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-extrabold text-white font-mono">{stats?.posts_delivered ?? 18}</span>
            <span className="text-xs text-zinc-500 ml-2">ta maqola</span>
          </div>
          <div className="mt-2 flex items-center text-[11px] text-emerald-400">
            <span>Deduplication bilan xavfsiz</span>
          </div>
        </div>

        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5 relative overflow-hidden">
          <div className="flex items-center justify-between text-zinc-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Tekshiruv Oralig'i</span>
            <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-extrabold text-white font-mono">5</span>
            <span className="text-xs text-zinc-500 ml-2">daqiqa (300s)</span>
          </div>
          <div className="mt-2 flex items-center text-[11px] text-purple-400">
            <span>ETag & Last-Modified tejamkorligi</span>
          </div>
        </div>
      </div>

      {/* Status Message Notification */}
      {statusMessage && (
        <div
          className={`p-3 rounded-lg flex items-center justify-between text-xs font-medium border ${
            statusMessage.type === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
          }`}
        >
          <div className="flex items-center space-x-2">
            {statusMessage.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-rose-400" />
            )}
            <span>{statusMessage.text}</span>
          </div>
          <button onClick={() => setStatusMessage(null)} className="text-zinc-400 hover:text-white text-xs">
            ✕
          </button>
        </div>
      )}

      {/* Add New Feed Form & OPML Import */}
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center space-x-2">
              <Plus className="w-4 h-4 text-orange-400" />
              <span>Yangi RSS / Atom Lenta Qo'shish</span>
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Sayt yoki RSS havolasini kiriting. Tizim avtomatik tarzda lentani aniqlaydi.
            </p>
          </div>

          <label className="cursor-pointer inline-flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 transition">
            <Upload className="w-3.5 h-3.5 text-orange-400" />
            <span>OPML Fayl Import Qilish</span>
            <input type="file" accept=".opml,.xml" className="hidden" onChange={handleFileUpload} />
          </label>
        </div>

        <form onSubmit={handleAdd} className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <div className="md:col-span-7">
            <input
              type="url"
              placeholder="https://kun.uz/news/rss yoki https://news.ycombinator.com/rss"
              value={newUrl}
              onChange={(e) => setNewUrl(e.target.value)}
              required
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3.5 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-orange-500/50"
            />
          </div>
          <div className="md:col-span-3">
            <input
              type="text"
              placeholder="Nomi (ixtiyoriy)"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3.5 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-orange-500/50"
            />
          </div>
          <div className="md:col-span-2">
            <button
              type="submit"
              disabled={submitting || !newUrl}
              className="w-full bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-black font-bold text-xs py-2 px-4 rounded-lg flex items-center justify-center space-x-1.5 transition"
            >
              {submitting ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Tekshirilmoqda...</span>
                </>
              ) : (
                <>
                  <Plus className="w-3.5 h-3.5" />
                  <span>Obuna Qo'shish</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Feeds Table */}
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">Kuzatilayotgan Lentalar</h3>
            <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-zinc-800 text-zinc-300">
              {feeds.length} ta
            </span>
          </div>
          <span className="text-xs text-zinc-400">Telegram orqali boshqarish: <code>/rss</code></span>
        </div>

        {feeds.length === 0 ? (
          <div className="p-12 text-center text-zinc-500">
            <Rss className="w-8 h-8 mx-auto mb-3 opacity-30 text-orange-400" />
            <p className="text-sm">Hozircha hech qanday RSS lenta qo'shilmagan.</p>
            <p className="text-xs text-zinc-600 mt-1">Yuqoridagi formadan yoki Telegramda <code>/sub &lt;url&gt;</code> buyrug'idan foydalaning.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-950/70 border-b border-zinc-800 text-zinc-400 uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-3 px-4">Lenta Nomi & Manba</th>
                  <th className="py-3 px-4">Feed Havolasi</th>
                  <th className="py-3 px-4 text-center">Obunachilar</th>
                  <th className="py-3 px-4">Oxirgi Tekshiruv</th>
                  <th className="py-3 px-4">Holat</th>
                  <th className="py-3 px-4 text-right">Amallar</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {feeds.map((feed) => {
                  const isBusy = actionFeedId === feed.id;
                  return (
                    <tr key={feed.id} className="hover:bg-zinc-800/30 transition-colors">
                      <td className="py-3 px-4">
                        <div className="flex items-center space-x-2">
                          <a
                            href={feed.link || feed.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-bold text-white hover:text-orange-400 flex items-center space-x-1"
                          >
                            <span>{feed.title || 'Nomsiz feed'}</span>
                            <ExternalLink className="w-3 h-3 text-zinc-500" />
                          </a>
                        </div>
                        {feed.description && (
                          <p className="text-[11px] text-zinc-500 line-clamp-1 mt-0.5">{feed.description}</p>
                        )}
                      </td>

                      <td className="py-3 px-4 font-mono text-zinc-400 max-w-[220px] truncate">
                        <div className="flex items-center space-x-1">
                          <span className="truncate">{feed.url}</span>
                          <button
                            onClick={() => handleCopy(feed.url, feed.id)}
                            className="text-zinc-500 hover:text-zinc-300 p-1"
                            title="Havolani nusxalash"
                          >
                            {copiedId === feed.id ? (
                              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                            ) : (
                              <Copy className="w-3 h-3" />
                            )}
                          </button>
                        </div>
                      </td>

                      <td className="py-3 px-4 text-center">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                          {feed.subscribers_count} ta chat
                        </span>
                      </td>

                      <td className="py-3 px-4 text-zinc-400 text-[11px]">
                        {feed.last_check ? new Date(feed.last_check).toLocaleTimeString() : 'Kutilmoqda'}
                      </td>

                      <td className="py-3 px-4">
                        {feed.error_count > 0 ? (
                          <span className="inline-flex items-center text-rose-400 text-[11px]">
                            <AlertTriangle className="w-3 h-3 mr-1" />
                            <span>Xato ({feed.error_count})</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center text-emerald-400 text-[11px]">
                            <CheckCircle2 className="w-3 h-3 mr-1" />
                            <span>Faol</span>
                          </span>
                        )}
                      </td>

                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end space-x-1">
                          <button
                            disabled={isBusy}
                            onClick={() => handleSync(feed.id)}
                            className="p-1.5 rounded text-zinc-400 hover:text-white hover:bg-zinc-800 transition disabled:opacity-50"
                            title="Hozir tekshirish"
                          >
                            <RefreshCw className={`w-3.5 h-3.5 ${isBusy ? 'animate-spin text-orange-400' : ''}`} />
                          </button>

                          <button
                            disabled={isBusy}
                            onClick={() => handleDelete(feed.id, feed.title)}
                            className="p-1.5 rounded text-zinc-500 hover:text-rose-400 hover:bg-zinc-800 transition disabled:opacity-50"
                            title="O'chirish"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
