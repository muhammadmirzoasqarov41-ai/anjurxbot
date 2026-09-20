import React, { useState, useEffect } from 'react';
import { api } from '../api';
import {
  Sparkles,
  Plus,
  Trash2,
  RefreshCw,
  Layers,
  Radio,
  Clock,
  CheckCircle2,
  AlertCircle,
  FileText,
  Image,
  Video,
  FileBox,
  Volume2,
  Mic,
  Clapperboard,
  Send,
  Eye,
  ExternalLink,
  ShieldCheck,
} from 'lucide-react';

interface CentralChannel {
  chat_id: number;
  title: string;
  username?: string | null;
  description?: string | null;
  active: boolean;
  added_by: number;
  created_at: string;
}

interface PremiumPost {
  id: string;
  central_chat_id: number;
  central_message_id: number;
  media_type: string;
  text: string;
  media_file_id: string | null;
  media_items?: Array<{ type: string; file_id: string }>;
  created_at: string;
  author_name?: string | null;
}

export const PremiumContentView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'channels' | 'posts'>('channels');
  const [centralChannels, setCentralChannels] = useState<CentralChannel[]>([]);
  const [posts, setPosts] = useState<PremiumPost[]>([]);
  const [postsTotal, setPostsTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New central channel modal
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [chatIdInput, setChatIdInput] = useState('');
  const [titleInput, setTitleInput] = useState('');
  const [usernameInput, setUsernameInput] = useState('');
  const [descInput, setDescInput] = useState('');
  const [saving, setSaving] = useState(false);

  const loadCentralChannels = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getCentralChannels();
      setCentralChannels(res.central_channels || []);
    } catch (err: any) {
      setError(err.message || 'Markaziy kanallarni yuklab bo‘lmadi');
    } finally {
      setLoading(false);
    }
  };

  const loadPremiumPosts = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getPremiumPosts(1, 30);
      setPosts(res.posts || []);
      setPostsTotal(res.total || 0);
    } catch (err: any) {
      setError(err.message || 'Premium postlarni yuklab bo‘lmadi');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'channels') {
      loadCentralChannels();
    } else {
      loadPremiumPosts();
    }
  }, [activeTab]);

  const handleAddChannel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatIdInput.trim() || !titleInput.trim()) {
      alert('Kanal ID va Nomini kiritish shart!');
      return;
    }

    try {
      setSaving(true);
      await api.addCentralChannel({
        chat_id: chatIdInput.trim(),
        title: titleInput.trim(),
        username: usernameInput.trim() || undefined,
        description: descInput.trim() || undefined,
      });
      setIsAddModalOpen(false);
      setChatIdInput('');
      setTitleInput('');
      setUsernameInput('');
      setDescInput('');
      loadCentralChannels();
    } catch (err: any) {
      alert(err.message || 'Kanalni qo‘shib bo‘lmadi');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteChannel = async (chatId: number, title: string) => {
    if (!window.confirm(`'${title}' markaziy kanalini o‘chirishni tasdiqlaysizmi?`)) return;
    try {
      await api.deleteCentralChannel(chatId);
      loadCentralChannels();
    } catch (err: any) {
      alert(err.message || 'Kanalni o‘chirib bo‘lmadi');
    }
  };

  const getMediaBadge = (type: string) => {
    switch (type) {
      case 'photo':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20"><Image className="w-3 h-3" /> Rasm</span>;
      case 'video':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-purple-500/10 text-purple-400 border border-purple-500/20"><Video className="w-3 h-3" /> Video</span>;
      case 'media_group':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-indigo-500/10 text-indigo-400 border border-indigo-500/20"><Layers className="w-3 h-3" /> Albom</span>;
      case 'document':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20"><FileBox className="w-3 h-3" /> Fayl</span>;
      case 'audio':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><Volume2 className="w-3 h-3" /> Audio</span>;
      case 'voice':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-rose-500/10 text-rose-400 border border-rose-500/20"><Mic className="w-3 h-3" /> Ovoz</span>;
      case 'animation':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"><Clapperboard className="w-3 h-3" /> GIF</span>;
      default:
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-zinc-800 text-zinc-300 border border-zinc-700"><FileText className="w-3 h-3" /> Matn</span>;
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-amber-500/10 via-zinc-900 to-zinc-900 border border-amber-500/20 rounded-xl p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-amber-500/20 text-amber-400 rounded-lg">
              <Sparkles className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                Premium Content Pool
                <span className="px-2 py-0.5 text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded-full">
                  Mustaqil Pool
                </span>
              </h2>
              <p className="text-sm text-zinc-400 mt-0.5">
                Markaziy "Postlar" kanalidan qabul qilingan original, qo‘lda tayyorlangan kontent
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => (activeTab === 'channels' ? loadCentralChannels() : loadPremiumPosts())}
              disabled={loading}
              className="px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-sm font-medium rounded-lg flex items-center gap-2 transition"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Yangilash
            </button>
            {activeTab === 'channels' && (
              <button
                onClick={() => setIsAddModalOpen(true)}
                className="px-3.5 py-2 bg-amber-600 hover:bg-amber-500 text-white text-sm font-semibold rounded-lg flex items-center gap-1.5 transition shadow-lg shadow-amber-900/20"
              >
                <Plus className="w-4 h-4" />
                Kanal qo‘shish
              </button>
            )}
          </div>
        </div>

        {/* Tab switcher */}
        <div className="flex gap-2 mt-5 border-t border-zinc-800 pt-4">
          <button
            onClick={() => setActiveTab('channels')}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium flex items-center gap-2 transition ${
              activeTab === 'channels'
                ? 'bg-amber-500 text-zinc-950 font-semibold'
                : 'text-zinc-400 hover:text-white bg-zinc-900/60'
            }`}
          >
            <Radio className="w-4 h-4" />
            Markaziy Kanallar ({centralChannels.length})
          </button>
          <button
            onClick={() => setActiveTab('posts')}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium flex items-center gap-2 transition ${
              activeTab === 'posts'
                ? 'bg-amber-500 text-zinc-950 font-semibold'
                : 'text-zinc-400 hover:text-white bg-zinc-900/60'
            }`}
          >
            <Layers className="w-4 h-4" />
            Premium Postlar Ombori ({postsTotal})
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm flex items-center gap-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* CHANNELS TAB */}
      {activeTab === 'channels' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {centralChannels.map((ch) => (
              <div
                key={ch.chat_id}
                className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col justify-between hover:border-zinc-700 transition"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="font-semibold text-white text-base flex items-center gap-1.5">
                        <Radio className="w-4 h-4 text-amber-400" />
                        {ch.title}
                      </h3>
                      {ch.username && (
                        <p className="text-xs text-amber-400/80 font-mono mt-0.5">
                          @{ch.username}
                        </p>
                      )}
                    </div>
                    <span className="px-2 py-0.5 text-xs rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> Faol
                    </span>
                  </div>

                  {ch.description && (
                    <p className="text-xs text-zinc-400 mt-2 line-clamp-2">
                      {ch.description}
                    </p>
                  )}

                  <div className="mt-4 pt-3 border-t border-zinc-800/80 text-xs text-zinc-500 space-y-1">
                    <p>ID: <span className="font-mono text-zinc-300">{ch.chat_id}</span></p>
                    <p>Qo‘shilgan: {new Date(ch.created_at).toLocaleDateString()}</p>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-zinc-800 flex items-center justify-between">
                  <span className="text-xs text-zinc-400 flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5 text-amber-400" /> Super Admin
                  </span>
                  <button
                    onClick={() => handleDeleteChannel(ch.chat_id, ch.title)}
                    className="p-1.5 text-zinc-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition"
                    title="Kanalni o‘chirish"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}

            {centralChannels.length === 0 && !loading && (
              <div className="col-span-full py-12 text-center bg-zinc-900/50 border border-dashed border-zinc-800 rounded-xl">
                <Radio className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
                <h4 className="text-base font-semibold text-zinc-300">Markaziy kanal hali ulanmagan</h4>
                <p className="text-sm text-zinc-500 max-w-md mx-auto mt-1 mb-4">
                  "Postlar" kanalini qo‘shing va @anjurxbot ni o‘sha kanalga admin qiling.
                </p>
                <button
                  onClick={() => setIsAddModalOpen(true)}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium rounded-lg inline-flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" /> Kanal ulash
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* POSTS TAB */}
      {activeTab === 'posts' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-zinc-400 px-1">
            <span>Jami: <b>{postsTotal} ta</b> saqlangan original post</span>
            <span>RSS 500-limitidan mustaqil</span>
          </div>

          <div className="space-y-3">
            {posts.map((p) => (
              <div
                key={p.id}
                className="bg-zinc-900 border border-zinc-800 hover:border-zinc-700 rounded-xl p-4 transition"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    {getMediaBadge(p.media_type)}
                    <span className="text-xs font-mono text-zinc-400">
                      Msg #{p.central_message_id}
                    </span>
                    {p.author_name && (
                      <span className="text-xs text-zinc-400">
                        • {p.author_name}
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-zinc-500 flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    {new Date(p.created_at).toLocaleString('uz-UZ')}
                  </span>
                </div>

                <div className="text-sm text-zinc-200 whitespace-pre-wrap line-clamp-4 font-sans bg-zinc-950/40 p-3 rounded-lg border border-zinc-800/60">
                  {p.text || <i className="text-zinc-500">(Faqat media, matnsiz)</i>}
                </div>

                {p.media_items && p.media_items.length > 0 && (
                  <div className="mt-2 text-xs text-zinc-400 flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-indigo-400" />
                    Albom tarkibida: {p.media_items.length} ta media fayl
                  </div>
                )}
              </div>
            ))}

            {posts.length === 0 && !loading && (
              <div className="py-12 text-center bg-zinc-900/50 border border-dashed border-zinc-800 rounded-xl">
                <Layers className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
                <h4 className="text-base font-semibold text-zinc-300">Premium postlar mavjud emas</h4>
                <p className="text-sm text-zinc-500 max-w-md mx-auto mt-1">
                  Markaziy kanalingizga adminlar post yuborganida ular bu yerda saqlanadi va huquqi bor user kanallariga taqsimlanadi.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Add Central Channel Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-zinc-950/80 backdrop-blur-sm">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-md p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
              <Radio className="w-5 h-5 text-amber-400" />
              Markaziy Kanalni Bazasiga Ulash
            </h3>
            <p className="text-xs text-zinc-400 mb-4">
              Ushbu kanal AnjurX uchun Central Content Pool bo‘lib xizmat qiladi. Botni o‘sha kanalga admin qilib qo‘shgan bo‘lishingiz kerak.
            </p>

            <form onSubmit={handleAddChannel} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">
                  Kanal Chat ID (masalan: <code>-1001234567890</code>) *
                </label>
                <input
                  type="text"
                  required
                  placeholder="-100..."
                  value={chatIdInput}
                  onChange={(e) => setChatIdInput(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">
                  Kanal Nomi *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Masalan: Postlar (Central)"
                  value={titleInput}
                  onChange={(e) => setTitleInput(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">
                  Kanal @Username (ixtiyoriy)
                </label>
                <input
                  type="text"
                  placeholder="postlar_markaziy"
                  value={usernameInput}
                  onChange={(e) => setUsernameInput(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">
                  Tavsif (ixtiyoriy)
                </label>
                <input
                  type="text"
                  placeholder="Qo‘lda tayyorlangan eksklyuziv kontent ombori"
                  value={descInput}
                  onChange={(e) => setDescInput(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-4 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm font-medium rounded-lg transition"
                >
                  Bekor qilish
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-sm font-semibold rounded-lg transition flex items-center gap-1.5"
                >
                  {saving ? 'Saqlanmoqda...' : 'Saqlash'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
