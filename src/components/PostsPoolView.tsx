import React, { useState, useEffect } from 'react';
import { PostItem } from '../types';
import { api } from '../api';
import {
  Layers,
  Search,
  ExternalLink,
  Clock,
  CheckCircle2,
  AlertCircle,
  X,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Trash2,
  Sparkles,
  ShieldAlert,
} from 'lucide-react';

interface PostsPoolViewProps {
  onRefresh: () => void;
}

export const PostsPoolView: React.FC<PostsPoolViewProps> = ({ onRefresh }) => {
  const [posts, setPosts] = useState<PostItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [cleaning, setCleaning] = useState(false);
  const [cleanNotice, setCleanNotice] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'queued' | 'assigned' | 'delivered' | 'failed' | 'expired'>('all');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [poolMax, setPoolMax] = useState(500);
  const [firestoreStatus, setFirestoreStatus] = useState<'online' | 'quota_exceeded' | 'standby'>('online');
  const [counts, setCounts] = useState({ all: 0, queued: 0, assigned: 0, delivered: 0, failed: 0, expired: 0 });
  const [selectedPost, setSelectedPost] = useState<PostItem | null>(null);

  const loadPosts = async () => {
    setLoading(true);
    try {
      const res = await api.getPosts({
        status: statusFilter,
        search,
        page,
        limit: 50,
      });
      setPosts(res.posts || []);
      setTotalPages(res.total_pages || 1);
      setTotalCount(res.total || 0);
      setPoolMax(res.pool_max || 500);
      if (res.firestore_status) setFirestoreStatus(res.firestore_status);
      setCounts(
        res.counts || {
          all: 0,
          queued: 0,
          assigned: 0,
          delivered: 0,
          failed: 0,
          expired: 0,
        }
      );
    } catch (err: any) {
      console.error('Error loading posts pool:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPosts();
  }, [statusFilter, page]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadPosts();
  };

  const handleCleanPool = async () => {
    if (cleaning) return;
    setCleaning(true);
    setCleanNotice(null);
    try {
      const res = await api.cleanupPostPool();
      setCleanNotice(res.message);
      await loadPosts();
      if (onRefresh) onRefresh();
      setTimeout(() => setCleanNotice(null), 6000);
    } catch (err: any) {
      console.error('Failed cleaning post pool:', err);
      setCleanNotice(`Tozalashda xatolik: ${err.message || 'Server xatosi'}`);
    } finally {
      setCleaning(false);
    }
  };

  const formatExpiry = (expiresAt: string) => {
    if (!expiresAt) return 'N/A';
    const diffMs = new Date(expiresAt).getTime() - Date.now();
    if (diffMs <= 0) return 'Muddati tugagan';
    const hours = Math.floor(diffMs / (1000 * 60 * 60));
    const days = Math.floor(hours / 24);
    if (days > 0) return `${days} kun ${hours % 24}s qoldi`;
    return `${hours} soat qoldi`;
  };

  const poolPercentage = Math.min(100, Math.round((counts.all / (poolMax || 500)) * 100));

  return (
    <div className="space-y-4 pb-20">
      {/* Quota Notice Banner if Exceeded */}
      {firestoreStatus === 'quota_exceeded' && (
        <div className="p-3.5 bg-amber-950/40 border border-amber-900/60 rounded-2xl flex items-start gap-3 text-amber-200">
          <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="text-xs">
            <h4 className="font-bold">Google Cloud Firestore Kvotasi To'ldi</h4>
            <p className="opacity-90 mt-0.5">
              Firestore bepul kvotasi (50,000 o'qish) chegarasiga yetdi. Post pool diskdagi barqaror va xavfsiz JSON xotirasida 500 ta limit bilan uzluksiz ishlamoqda.
            </p>
          </div>
        </div>
      )}

      {/* Header & Capacity Card */}
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-4 shadow-sm space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
              <Layers className="w-5 h-5 text-indigo-400" />
              <span>Post Pool (Maksimum 500 ta post)</span>
            </h2>
            <p className="text-xs text-zinc-400 mt-0.5">
              Yangi postlar ustuvor. 500 tadan oshganda eski va yetkazilgan postlar avtomatik tozalanadi.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCleanPool}
              disabled={cleaning}
              className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors disabled:opacity-50 shrink-0"
            >
              {cleaning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5 text-rose-400" />}
              <span>{cleaning ? 'Tozalanmoqda...' : 'Poolni Tozalash'}</span>
            </button>

            {/* Search */}
            <form onSubmit={handleSearchSubmit} className="relative w-full sm:w-56">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Qidiruv..."
                className="w-full pl-8 pr-3 py-1.5 bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
              />
              <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-2" />
            </form>
          </div>
        </div>

        {/* Pool Capacity Bar */}
        <div className="space-y-1.5 pt-1">
          <div className="flex items-center justify-between text-xs">
            <span className="text-zinc-400 font-medium">Hovuz to'laligi:</span>
            <span className="font-mono text-zinc-200 font-bold">
              {counts.all} / {poolMax} post ({poolPercentage}%)
            </span>
          </div>
          <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${
                poolPercentage > 90 ? 'bg-amber-500' : 'bg-indigo-500'
              }`}
              style={{ width: `${poolPercentage}%` }}
            />
          </div>
        </div>

        {cleanNotice && (
          <div className="p-2.5 bg-emerald-950/40 border border-emerald-800/60 rounded-xl text-xs text-emerald-300 flex items-center gap-2">
            <Sparkles className="w-4 h-4 shrink-0 text-emerald-400" />
            <span>{cleanNotice}</span>
          </div>
        )}
      </div>

      {/* Status Segmented Tabs with Counts */}
      <div className="flex items-center gap-1.5 p-1 bg-zinc-900/90 border border-zinc-800 rounded-xl overflow-x-auto">
        {(
          [
            { id: 'all', label: `Barchasi (${counts.all})` },
            { id: 'queued', label: `Navbatda (${counts.queued})` },
            { id: 'assigned', label: `Biriktirilgan (${counts.assigned || 0})` },
            { id: 'delivered', label: `Yetkazilgan (${counts.delivered})` },
            { id: 'failed', label: `Xatolik (${counts.failed || 0})` },
            { id: 'expired', label: `Muddati o‘tgan (${counts.expired})` },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            onClick={() => {
              setStatusFilter(tab.id);
              setPage(1);
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors shrink-0 ${
              statusFilter === tab.id
                ? 'bg-zinc-800 text-white shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Posts List */}
      {loading ? (
        <div className="py-16 text-center text-zinc-500 flex flex-col items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-500 mb-2" />
          <span className="text-xs">Postlar yuklanmoqda...</span>
        </div>
      ) : posts.length === 0 ? (
        <div className="py-12 bg-zinc-900/40 border border-zinc-800/80 rounded-2xl text-center text-zinc-500 text-xs p-6">
          <Layers className="w-8 h-8 mx-auto text-zinc-600 mb-2" />
          <span>Bu bo‘limda hozircha postlar yo‘q</span>
        </div>
      ) : (
        <div className="space-y-3">
          {posts.map((post) => {
            const isQueued = post.status === 'queued';
            const isDelivered = post.status === 'delivered';
            const isAssigned = post.status === 'assigned';
            const isFailed = post.status === 'failed';

            return (
              <div
                key={post.post_id}
                onClick={() => setSelectedPost(post)}
                className="bg-zinc-900/90 border border-zinc-800 hover:border-zinc-700 rounded-2xl p-4 cursor-pointer transition-all flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300">
                      {post.source_name || post.source_id.replace('src_', '')}
                    </span>

                    <span
                      className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                        isQueued
                          ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/30'
                          : isAssigned
                          ? 'bg-blue-500/10 text-blue-400 border border-blue-500/30'
                          : isDelivered
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                          : isFailed
                          ? 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                          : 'bg-zinc-800 text-zinc-400'
                      }`}
                    >
                      {isQueued
                        ? 'Navbatda'
                        : isAssigned
                        ? 'Biriktirilgan'
                        : isDelivered
                        ? 'Yetkazilgan'
                        : isFailed
                        ? 'Xatolik'
                        : 'Muddati o‘tgan'}
                    </span>
                  </div>

                  <h3 className="text-xs font-semibold text-white line-clamp-2 leading-relaxed">
                    {post.title}
                  </h3>

                  <div className="flex items-center gap-3 text-[11px] text-zinc-500 mt-1.5 font-mono">
                    <span>
                      Yuklangan: {new Date(post.fetched_at).toLocaleDateString('uz-UZ')}
                    </span>
                    <span>Saqlanish: {formatExpiry(post.expires_at)}</span>
                  </div>
                </div>

                {post.image_url && (
                  <img
                    src={post.image_url}
                    alt=""
                    className="w-16 h-12 object-cover rounded-lg shrink-0 border border-zinc-800"
                    referrerPolicy="no-referrer"
                  />
                )}
              </div>
            );
          })}

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1.5 bg-zinc-900 border border-zinc-800 text-zinc-300 rounded-xl text-xs flex items-center gap-1 disabled:opacity-40"
              >
                <ChevronLeft className="w-4 h-4" />
                <span>Oldingi</span>
              </button>

              <span className="text-xs text-zinc-500 font-mono">
                Sahifa {page} / {totalPages} (Jami {totalCount} ta)
              </span>

              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 bg-zinc-900 border border-zinc-800 text-zinc-300 rounded-xl text-xs flex items-center gap-1 disabled:opacity-40"
              >
                <span>Keyingi</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      )}

      {/* Post Details Modal */}
      {selectedPost && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-lg w-full max-h-[85vh] overflow-y-auto p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <span className="text-xs font-semibold text-zinc-400">Post Tafsilotlari</span>
              <button
                onClick={() => setSelectedPost(null)}
                className="text-zinc-400 hover:text-white p-1 rounded-lg hover:bg-zinc-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {selectedPost.image_url && (
              <img
                src={selectedPost.image_url}
                alt=""
                className="w-full h-48 object-cover rounded-xl border border-zinc-800"
                referrerPolicy="no-referrer"
              />
            )}

            <div>
              <span className="text-[11px] font-bold text-indigo-400">
                {selectedPost.source_name || selectedPost.source_id}
              </span>
              <h2 className="text-sm font-bold text-white mt-1 leading-snug">
                {selectedPost.title}
              </h2>
            </div>

            {selectedPost.description && (
              <p className="text-xs text-zinc-300 leading-relaxed whitespace-pre-line">
                {selectedPost.description}
              </p>
            )}

            <div className="grid grid-cols-2 gap-2 text-[11px] bg-zinc-950 p-3 rounded-xl border border-zinc-800 font-mono">
              <div>
                <span className="text-zinc-500 block">Holat:</span>
                <span className="text-zinc-200 capitalize font-bold">{selectedPost.status}</span>
              </div>
              <div>
                <span className="text-zinc-500 block">Yuklangan:</span>
                <span className="text-zinc-200">
                  {new Date(selectedPost.fetched_at).toLocaleString('uz-UZ')}
                </span>
              </div>
              <div>
                <span className="text-zinc-500 block">Saqlanish:</span>
                <span className="text-zinc-200">{formatExpiry(selectedPost.expires_at)}</span>
              </div>
              <div>
                <span className="text-zinc-500 block">Urinishlar soni:</span>
                <span className="text-zinc-200">{selectedPost.attempts} ta</span>
              </div>
            </div>

            {selectedPost.url && (
              <a
                href={selectedPost.url}
                target="_blank"
                rel="noreferrer"
                className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
              >
                <span>Asl maqolani ochish</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
