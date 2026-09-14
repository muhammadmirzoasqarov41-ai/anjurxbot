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
  Calendar,
} from 'lucide-react';

interface PostsPoolViewProps {
  onRefresh: () => void;
}

export const PostsPoolView: React.FC<PostsPoolViewProps> = () => {
  const [posts, setPosts] = useState<PostItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'queued' | 'delivered' | 'expired'>('all');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [counts, setCounts] = useState({ all: 0, queued: 0, delivered: 0, expired: 0 });
  const [selectedPost, setSelectedPost] = useState<PostItem | null>(null);

  const loadPosts = async () => {
    setLoading(true);
    try {
      const res = await api.getPosts({
        status: statusFilter,
        search,
        page,
        limit: 15,
      });
      setPosts(res.posts || []);
      setTotalPages(res.total_pages || 1);
      setCounts(res.counts || { all: 0, queued: 0, delivered: 0, expired: 0 });
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

  const formatExpiry = (expiresAt: string) => {
    if (!expiresAt) return 'N/A';
    const diffMs = new Date(expiresAt).getTime() - Date.now();
    if (diffMs <= 0) return 'Muddati tugagan';
    const hours = Math.floor(diffMs / (1000 * 60 * 60));
    const days = Math.floor(hours / 24);
    if (days > 0) return `${days} kun ${hours % 24}s qoldi`;
    return `${hours} soat qoldi`;
  };

  return (
    <div className="space-y-4 pb-20">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <Layers className="w-5 h-5 text-indigo-400" />
            <span>Post Pool (5 Kunlik Hovuz)</span>
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            5 kun davomida saqlanadi, har bir kanalga faqat bir marta yuboriladi
          </p>
        </div>

        {/* Search */}
        <form onSubmit={handleSearchSubmit} className="relative w-full sm:w-64">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Sarlavha yoki URL..."
            className="w-full pl-8 pr-3 py-2 bg-zinc-900 border border-zinc-800 rounded-xl text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
          />
          <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-2.5" />
        </form>
      </div>

      {/* Status Segmented Tabs with Counts */}
      <div className="flex items-center gap-1.5 p-1 bg-zinc-900/90 border border-zinc-800 rounded-xl overflow-x-auto">
        {(
          [
            { id: 'all', label: `Barchasi (${counts.all})` },
            { id: 'queued', label: `Navbatda (${counts.queued})` },
            { id: 'delivered', label: `Yetkazilgan (${counts.delivered})` },
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
                          : isDelivered
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                          : 'bg-zinc-800 text-zinc-400'
                      }`}
                    >
                      {isQueued ? 'Navbatda' : isDelivered ? 'Yetkazilgan' : 'Muddati o‘tgan'}
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
                Sahifa {page} / {totalPages}
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

      {/* Post Detail Modal */}
      {selectedPost && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-t-3xl sm:rounded-2xl w-full max-w-lg max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-in slide-in-from-bottom duration-200">
            <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-zinc-800 text-zinc-300">
                  {selectedPost.source_name || selectedPost.source_id}
                </span>
                <span className="text-xs text-zinc-400 font-mono">ID: {selectedPost.post_id}</span>
              </div>
              <button
                onClick={() => setSelectedPost(null)}
                className="p-1.5 text-zinc-400 hover:text-white rounded-xl bg-zinc-900"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 overflow-y-auto space-y-4 text-xs">
              {selectedPost.image_url && (
                <img
                  src={selectedPost.image_url}
                  alt=""
                  className="w-full max-h-48 object-cover rounded-xl border border-zinc-800"
                  referrerPolicy="no-referrer"
                />
              )}

              <h2 className="text-base font-bold text-white leading-snug">
                {selectedPost.title}
              </h2>

              {selectedPost.description && (
                <div className="text-zinc-300 leading-relaxed bg-zinc-900/50 p-3 rounded-xl border border-zinc-800/80">
                  {selectedPost.description}
                </div>
              )}

              <div className="bg-zinc-900 p-3 rounded-xl space-y-1.5 font-mono text-[11px]">
                <div className="flex justify-between text-zinc-400">
                  <span>Holati:</span>
                  <span className="text-white uppercase font-bold">{selectedPost.status}</span>
                </div>
                <div className="flex justify-between text-zinc-400">
                  <span>Yuklangan vaqti:</span>
                  <span className="text-white">
                    {new Date(selectedPost.fetched_at).toLocaleString('uz-UZ')}
                  </span>
                </div>
                <div className="flex justify-between text-zinc-400">
                  <span>Saqlanish muddati:</span>
                  <span className="text-white">{formatExpiry(selectedPost.expires_at)}</span>
                </div>
                {selectedPost.delivered_at && (
                  <div className="flex justify-between text-zinc-400">
                    <span>Yetkazilgan:</span>
                    <span className="text-emerald-400">
                      {new Date(selectedPost.delivered_at).toLocaleString('uz-UZ')}
                    </span>
                  </div>
                )}
                {selectedPost.assigned_channel_id && (
                  <div className="flex justify-between text-zinc-400">
                    <span>Biriktirilgan kanal:</span>
                    <span className="text-white">{selectedPost.assigned_channel_id}</span>
                  </div>
                )}
              </div>

              {selectedPost.url && (
                <a
                  href={selectedPost.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-full py-2.5 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-white font-medium rounded-xl flex items-center justify-center gap-2 transition-colors"
                >
                  <span>Asl Maqolani Ko‘rish</span>
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
