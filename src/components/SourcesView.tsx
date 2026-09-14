import React, { useState, useEffect, useRef } from 'react';
import { SourceItem, CategoryItem, TestFeedResult } from '../types';
import { api } from '../api';
import {
  Rss,
  Plus,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Trash2,
  Download,
  Upload,
  ExternalLink,
  X,
  Loader2,
  FolderPlus,
  Folder,
  Globe,
  Check,
  Edit2,
  Radio,
  Layers,
  Sparkles,
} from 'lucide-react';

interface SourcesViewProps {
  onRefresh: () => void;
}

export const SourcesView: React.FC<SourcesViewProps> = ({ onRefresh }) => {
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeCategoryTab, setActiveCategoryTab] = useState<string>('all');

  // Sync state
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [syncingAll, setSyncingAll] = useState(false);

  // Messages
  const [message, setMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Source Modal (Add / Edit)
  const [showSourceModal, setShowSourceModal] = useState(false);
  const [editingSource, setEditingSource] = useState<SourceItem | null>(null);
  const [formName, setFormName] = useState('');
  const [formFeedUrl, setFormFeedUrl] = useState('');
  const [formWebsiteUrl, setFormWebsiteUrl] = useState('');
  const [formCategoryId, setFormCategoryId] = useState('');
  const [formLanguage, setFormLanguage] = useState('uz');
  const [formType, setFormType] = useState('rss');
  const [formActive, setFormActive] = useState(true);
  const [savingSource, setSavingSource] = useState(false);

  // Test Feed State
  const [testingFeed, setTestingFeed] = useState(false);
  const [testResult, setTestResult] = useState<TestFeedResult | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  // Category Management Modal
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [editingCategory, setEditingCategory] = useState<CategoryItem | null>(null);
  const [catName, setCatName] = useState('');
  const [catIcon, setCatIcon] = useState('📰');
  const [catDesc, setCatDesc] = useState('');
  const [catSortOrder, setCatSortOrder] = useState(0);
  const [savingCategory, setSavingCategory] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadData = async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const [srcRes, catRes] = await Promise.all([
        api.getSources(),
        api.getCategories(),
      ]);
      setSources(srcRes.sources || []);
      setCategories(catRes.categories || []);
      if (catRes.categories?.length > 0 && !formCategoryId) {
        setFormCategoryId(catRes.categories[0].id);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Ma‘lumotlarni yuklab bo‘lmadi');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // --- Source Operations ---
  const handleOpenAddSource = () => {
    setEditingSource(null);
    setFormName('');
    setFormFeedUrl('');
    setFormWebsiteUrl('');
    setFormCategoryId(categories[0]?.id || 'cat_ozbekiston');
    setFormLanguage('uz');
    setFormType('rss');
    setFormActive(true);
    setTestResult(null);
    setTestError(null);
    setShowSourceModal(true);
  };

  const handleOpenEditSource = (src: SourceItem) => {
    setEditingSource(src);
    setFormName(src.name);
    setFormFeedUrl(src.feed_url || src.url);
    setFormWebsiteUrl(src.website_url || '');
    setFormCategoryId(src.category_id || categories[0]?.id || 'cat_ozbekiston');
    setFormLanguage(src.language || 'uz');
    setFormType(src.type || 'rss');
    setFormActive(src.active);
    setTestResult(null);
    setTestError(null);
    setShowSourceModal(true);
  };

  const handleTestFeed = async (urlToTest?: string) => {
    const targetUrl = urlToTest || formFeedUrl.trim();
    if (!targetUrl) {
      setTestError('Iltimos, RSS / Feed URL manzilini kiriting');
      return;
    }

    setTestingFeed(true);
    setTestResult(null);
    setTestError(null);

    try {
      const result = await api.testFeed(targetUrl);
      setTestResult(result);
      if (result.status === 'error') {
        setTestError(result.error || 'Feedga ulanib bo‘lmadi');
      } else if (result.format && formType === 'rss') {
        // Auto-suggest format
        if (result.format.toLowerCase().includes('atom')) setFormType('atom');
        else if (result.format.toLowerCase().includes('json')) setFormType('json');
      }
    } catch (err: any) {
      setTestError(err.message || 'Feedni tekshirishda xatolik yuz berdi');
    } finally {
      setTestingFeed(false);
    }
  };

  const handleSaveSource = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim() || !formFeedUrl.trim()) return;

    setSavingSource(true);
    setMessage(null);
    setErrorMessage(null);

    try {
      const selectedCat = categories.find((c) => c.id === formCategoryId);
      const payload: any = {
        name: formName.trim(),
        url: formFeedUrl.trim(),
        feed_url: formFeedUrl.trim(),
        website_url: formWebsiteUrl.trim(),
        category_id: formCategoryId,
        category: selectedCat ? selectedCat.name : 'Yangiliklar',
        language: formLanguage,
        type: formType,
        active: formActive,
      };

      if (editingSource) {
        await api.updateSource(editingSource.id, payload);
        setMessage(`"${formName}" muvaffaqiyatli yangilandi`);
      } else {
        await api.addSource(payload);
        setMessage(`"${formName}" muvaffaqiyatli qo‘shildi`);
      }

      setShowSourceModal(false);
      await loadData();
      onRefresh();
    } catch (err: any) {
      setErrorMessage(err.message || 'Manbani saqlashda xatolik yuz berdi');
    } finally {
      setSavingSource(false);
    }
  };

  const handleToggle = async (id: string) => {
    try {
      const res = await api.toggleSource(id);
      setSources((prev) =>
        prev.map((s) => (s.id === id ? { ...s, active: res.active } : s))
      );
      onRefresh();
    } catch (err: any) {
      alert(err.message || 'Xatolik yuz berdi');
    }
  };

  const handleSyncSource = async (id: string) => {
    setSyncingId(id);
    setMessage(null);
    setErrorMessage(null);
    try {
      const res = await api.syncSource(id);
      setSources((prev) => prev.map((s) => (s.id === id ? res.source : s)));
      setMessage(res.message);
      onRefresh();
    } catch (err: any) {
      setErrorMessage(err.message || 'Sinxronlashda xatolik yuz berdi');
    } finally {
      setSyncingId(null);
    }
  };

  const handleSyncAll = async () => {
    setSyncingAll(true);
    setMessage(null);
    setErrorMessage(null);
    try {
      const res = await api.syncAllSources();
      await loadData();
      setMessage(res.message);
      onRefresh();
    } catch (err: any) {
      setErrorMessage(err.message || 'Barcha manbalarni sinxronlashda xatolik');
    } finally {
      setSyncingAll(false);
    }
  };

  const handleDeleteSource = async (id: string, name: string) => {
    if (!window.confirm(`"${name}" manbasini rostdan ham o‘chirmoqchimisiz?`)) return;
    try {
      await api.deleteSource(id);
      setSources((prev) => prev.filter((s) => s.id !== id));
      setMessage(`"${name}" o‘chirildi`);
      onRefresh();
    } catch (err: any) {
      alert(err.message || 'O‘chirishda xatolik yuz berdi');
    }
  };

  // --- Category Operations ---
  const handleOpenAddCategory = () => {
    setEditingCategory(null);
    setCatName('');
    setCatIcon('📁');
    setCatDesc('');
    setCatSortOrder(categories.length + 1);
    setShowCategoryModal(true);
  };

  const handleOpenEditCategory = (cat: CategoryItem) => {
    setEditingCategory(cat);
    setCatName(cat.name);
    setCatIcon(cat.icon || '📁');
    setCatDesc(cat.description || '');
    setCatSortOrder(cat.sort_order || 0);
    setShowCategoryModal(true);
  };

  const handleSaveCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!catName.trim()) return;

    setSavingCategory(true);
    try {
      if (editingCategory) {
        await api.updateCategory(editingCategory.id, {
          name: catName.trim(),
          icon: catIcon.trim(),
          description: catDesc.trim(),
          sort_order: catSortOrder,
        });
        setMessage(`Kategoriya "${catName}" yangilandi`);
      } else {
        await api.createCategory({
          name: catName.trim(),
          icon: catIcon.trim(),
          description: catDesc.trim(),
        });
        setMessage(`Yangi kategoriya "${catName}" yaratildi`);
      }
      setShowCategoryModal(false);
      await loadData();
      onRefresh();
    } catch (err: any) {
      alert(err.message || 'Kategoriyani saqlab bo‘lmadi');
    } finally {
      setSavingCategory(false);
    }
  };

  const handleDeleteCategory = async (id: string, name: string) => {
    if (!window.confirm(`"${name}" kategoriyasini o‘chirishni xohlaysizmi?\nIchidagi manbalar saqlanib qoladi.`)) return;
    try {
      await api.deleteCategory(id);
      setMessage(`Kategoriya "${name}" o‘chirildi`);
      await loadData();
      onRefresh();
    } catch (err: any) {
      alert(err.message || 'Kategoriyani o‘chirib bo‘lmadi');
    }
  };

  // OPML
  const handleExportOpml = async () => {
    try {
      const blob = await api.exportOpml();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `anjurx_feeds_${new Date().toISOString().slice(0, 10)}.opml`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(err.message || 'OPML eksport qilib bo‘lmadi');
    }
  };

  const handleImportOpml = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const res = await api.importOpml(file);
      await loadData();
      setMessage(res.message);
      onRefresh();
    } catch (err: any) {
      alert(err.message || 'OPML import qilib bo‘lmadi');
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Filter sources by active category tab
  const filteredSources = sources.filter((s) => {
    if (activeCategoryTab === 'all') return true;
    if (s.category_id === activeCategoryTab) return true;
    const cat = categories.find((c) => c.id === activeCategoryTab);
    return cat && (s.category || '').toLowerCase() === cat.name.toLowerCase();
  });

  return (
    <div className="space-y-4 pb-20">
      {/* Header & Main Control Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-zinc-900/60 border border-zinc-800/80 p-4 rounded-2xl">
        <div>
          <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <Rss className="w-5 h-5 text-amber-400" />
            <span>Manbalar & RSS Tizimi</span>
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Jami <b>{sources.length}</b> ta manba, <b>{categories.length}</b> ta kategoriya boshqaruvda
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={handleOpenAddSource}
            className="px-3.5 py-2 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold rounded-xl text-xs flex items-center gap-1.5 transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4 stroke-[2.5]" />
            <span>Yangi Manba</span>
          </button>

          <button
            onClick={handleOpenAddCategory}
            className="px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-100 rounded-xl text-xs flex items-center gap-1.5 transition-colors border border-zinc-700"
          >
            <FolderPlus className="w-3.5 h-3.5 text-amber-400" />
            <span>Kategoriya Qo‘shish</span>
          </button>

          <button
            onClick={handleSyncAll}
            disabled={syncingAll}
            className="px-3 py-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-zinc-200 rounded-xl text-xs flex items-center gap-1.5 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncingAll ? 'animate-spin text-amber-400' : ''}`} />
            <span>Barchasini Sinxronlash</span>
          </button>

          <button
            onClick={handleExportOpml}
            title="OPML formatida yuklab olish"
            className="p-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 rounded-xl transition-colors"
          >
            <Download className="w-4 h-4" />
          </button>

          <button
            onClick={() => fileInputRef.current?.click()}
            title="OPML fayldan import qilish"
            className="p-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 rounded-xl transition-colors"
          >
            <Upload className="w-4 h-4" />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".opml,.xml"
            onChange={handleImportOpml}
            className="hidden"
          />
        </div>
      </div>

      {/* Messages */}
      {message && (
        <div className="p-3 bg-emerald-950/40 border border-emerald-900/60 rounded-xl text-xs text-emerald-300 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{message}</span>
          </div>
          <button onClick={() => setMessage(null)} className="text-emerald-400 hover:text-white">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
      {errorMessage && (
        <div className="p-3 bg-red-950/40 border border-red-900/60 rounded-xl text-xs text-red-300 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button onClick={() => setErrorMessage(null)} className="text-red-400 hover:text-white">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Category Tabs Bar */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
        <button
          onClick={() => setActiveCategoryTab('all')}
          className={`px-3 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-colors flex items-center gap-1.5 border ${
            activeCategoryTab === 'all'
              ? 'bg-zinc-100 text-zinc-950 border-zinc-100 font-semibold'
              : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-white'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Barchasi</span>
          <span className="text-[10px] px-1.5 py-0.2 bg-black/10 rounded-full font-mono">
            {sources.length}
          </span>
        </button>

        {categories.map((cat) => {
          const count = sources.filter(
            (s) => s.category_id === cat.id || (s.category || '').toLowerCase() === cat.name.toLowerCase()
          ).length;
          const isActiveTab = activeCategoryTab === cat.id;

          return (
            <div key={cat.id} className="flex items-center shrink-0">
              <button
                onClick={() => setActiveCategoryTab(cat.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-colors flex items-center gap-1.5 border ${
                  isActiveTab
                    ? 'bg-emerald-500 text-zinc-950 border-emerald-400 font-semibold'
                    : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-white'
                }`}
              >
                <span>{cat.icon || '📁'}</span>
                <span>{cat.name}</span>
                <span
                  className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                    isActiveTab ? 'bg-zinc-950/20 text-zinc-950' : 'bg-zinc-800 text-zinc-400'
                  }`}
                >
                  {count}
                </span>
              </button>
            </div>
          );
        })}
      </div>

      {/* Active Category Header with Edit/Delete Controls if specific category selected */}
      {activeCategoryTab !== 'all' && (
        (() => {
          const curCat = categories.find((c) => c.id === activeCategoryTab);
          if (!curCat) return null;
          return (
            <div className="flex items-center justify-between bg-zinc-900/40 border border-zinc-800/80 px-4 py-2.5 rounded-xl text-xs">
              <div className="flex items-center gap-2">
                <span className="text-lg">{curCat.icon || '📁'}</span>
                <div>
                  <span className="font-bold text-white block">{curCat.name}</span>
                  {curCat.description && (
                    <span className="text-zinc-500 text-[11px] block">{curCat.description}</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => handleOpenEditCategory(curCat)}
                  className="px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-[11px] flex items-center gap-1"
                >
                  <Edit2 className="w-3 h-3" />
                  <span>Tahrirlash</span>
                </button>
                <button
                  onClick={() => handleDeleteCategory(curCat.id, curCat.name)}
                  className="px-2.5 py-1 bg-zinc-800 hover:bg-red-950/40 text-zinc-400 hover:text-red-300 rounded-lg text-[11px] flex items-center gap-1"
                >
                  <Trash2 className="w-3 h-3" />
                  <span>O‘chirish</span>
                </button>
              </div>
            </div>
          );
        })()
      )}

      {/* Sources List / Tree */}
      {loading ? (
        <div className="py-20 text-center text-zinc-500 flex flex-col items-center justify-center">
          <Loader2 className="w-7 h-7 animate-spin text-amber-500 mb-2" />
          <span className="text-xs">Manbalar yuklanmoqda...</span>
        </div>
      ) : filteredSources.length === 0 ? (
        <div className="py-14 bg-zinc-900/40 border border-zinc-800/80 rounded-2xl text-center text-zinc-500 text-xs p-6 space-y-3">
          <Rss className="w-9 h-9 mx-auto text-zinc-600" />
          <p className="font-medium text-zinc-400">Bu kategoriyada manbalar mavjud emas</p>
          <button
            onClick={handleOpenAddSource}
            className="px-3.5 py-2 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold rounded-xl text-xs inline-flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Manba qo‘shish</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filteredSources.map((source) => {
            const isSyncing = syncingId === source.id;
            const hasError = !!source.last_error || source.error_count > 0;
            const cat = categories.find(
              (c) => c.id === source.category_id || c.name.toLowerCase() === (source.category || '').toLowerCase()
            );

            return (
              <div
                key={source.id}
                className="bg-zinc-900/90 border border-zinc-800 hover:border-zinc-700/80 rounded-2xl p-4 transition-all flex flex-col justify-between"
              >
                <div>
                  {/* Top Row: Title, Category, Status Switch */}
                  <div className="flex items-start justify-between gap-2.5 mb-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-sm font-bold text-white tracking-tight truncate">
                          {source.name}
                        </h3>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300 border border-zinc-700 font-medium">
                          {cat?.icon || '📁'} {cat?.name || source.category}
                        </span>
                        <span className="text-[10px] uppercase px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 font-mono">
                          {source.type || 'rss'}
                        </span>
                        {source.language && (
                          <span className="text-[10px] uppercase px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono">
                            {source.language}
                          </span>
                        )}
                      </div>

                      {/* Links Row */}
                      <div className="flex items-center gap-3 mt-1 text-[11px] text-zinc-500">
                        {source.website_url && (
                          <a
                            href={source.website_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-zinc-300 flex items-center gap-1 truncate max-w-[160px]"
                          >
                            <Globe className="w-3 h-3 shrink-0" />
                            <span className="truncate">{source.website_url.replace(/^https?:\/\//, '')}</span>
                          </a>
                        )}
                        <a
                          href={source.feed_url || source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:text-amber-300 flex items-center gap-1 truncate max-w-[200px]"
                        >
                          <Rss className="w-3 h-3 shrink-0 text-amber-400" />
                          <span className="truncate">{source.feed_url || source.url}</span>
                          <ExternalLink className="w-2.5 h-2.5 shrink-0 opacity-70" />
                        </a>
                      </div>
                    </div>

                    {/* Active Toggle Button */}
                    <button
                      onClick={() => handleToggle(source.id)}
                      className={`text-[11px] px-2.5 py-1 rounded-full font-medium border shrink-0 transition-colors ${
                        source.active
                          ? 'bg-emerald-950/50 text-emerald-400 border-emerald-800/60'
                          : 'bg-zinc-800 text-zinc-400 border-zinc-700'
                      }`}
                    >
                      {source.active ? 'Faol' : 'To‘xtatilgan'}
                    </button>
                  </div>

                  {/* Error Indicator if any */}
                  {hasError && (
                    <div className="my-2 p-2 bg-red-950/30 border border-red-900/50 rounded-xl text-[11px] text-red-300 flex items-start gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />
                      <div className="min-w-0 flex-1">
                        <span className="font-semibold block">
                          Ulanish xatosi ({source.error_count} marta):
                        </span>
                        <span className="text-zinc-400 line-clamp-1">{source.last_error}</span>
                      </div>
                    </div>
                  )}

                  {/* Health Metrics Strip */}
                  <div className="grid grid-cols-2 gap-2 mt-3 pt-2.5 border-t border-zinc-800/70 text-[11px]">
                    <div>
                      <span className="text-zinc-500 block text-[10px]">Oxirgi fetch</span>
                      <span className="text-zinc-300 font-mono">
                        {source.last_fetch_at
                          ? new Date(source.last_fetch_at).toLocaleTimeString('uz-UZ', {
                              hour: '2-digit',
                              minute: '2-digit',
                              second: '2-digit',
                            })
                          : '—'}
                      </span>
                    </div>
                    <div>
                      <span className="text-zinc-500 block text-[10px]">Pulladagi postlar</span>
                      <span className="text-emerald-400 font-mono font-semibold">
                        {source.posts_count || 0} ta post
                      </span>
                    </div>
                  </div>
                </div>

                {/* Card Actions Footer */}
                <div className="mt-3 pt-2.5 border-t border-zinc-800/70 flex items-center justify-between gap-1">
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => handleSyncSource(source.id)}
                      disabled={isSyncing}
                      className="px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg text-xs flex items-center gap-1 transition-colors"
                      title="Hoziroq tekshirish"
                    >
                      <RefreshCw className={`w-3 h-3 ${isSyncing ? 'animate-spin text-amber-400' : ''}`} />
                      <span>{isSyncing ? 'Yuklanmoqda...' : 'Fetch'}</span>
                    </button>

                    <button
                      onClick={() => handleTestFeed(source.feed_url || source.url)}
                      className="px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-xs flex items-center gap-1 transition-colors"
                      title="Feed test qilish"
                    >
                      <Sparkles className="w-3 h-3 text-amber-400" />
                      <span>Test</span>
                    </button>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleOpenEditSource(source)}
                      className="p-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg transition-colors"
                      title="Tahrirlash"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleDeleteSource(source.id, source.name)}
                      className="p-1.5 bg-zinc-800 hover:bg-red-950/50 hover:text-red-400 text-zinc-400 rounded-lg transition-colors"
                      title="O‘chirish"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Modal 1: Add / Edit Source Modal */}
      {showSourceModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-t-3xl sm:rounded-2xl w-full max-w-lg p-5 shadow-2xl animate-in slide-in-from-bottom duration-200 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Rss className="w-4 h-4 text-amber-400" />
                <span>{editingSource ? 'Manbani Tahrirlash' : 'Yangi RSS Manba Qo‘shish'}</span>
              </h3>
              <button
                onClick={() => setShowSourceModal(false)}
                className="p-1.5 text-zinc-400 hover:text-white rounded-xl bg-zinc-900"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveSource} className="space-y-3.5 text-xs pt-3">
              {/* Category Dropdown */}
              <div>
                <label className="block text-zinc-400 mb-1 font-medium">Kategoriya</label>
                <select
                  value={formCategoryId}
                  onChange={(e) => setFormCategoryId(e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-xl text-white text-xs focus:outline-none focus:border-emerald-500"
                  required
                >
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.icon || '📁'} {cat.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Source Name */}
              <div>
                <label className="block text-zinc-400 mb-1 font-medium">Manba Nomi</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="Masalan: Kun.uz"
                  className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-xl text-white text-xs focus:outline-none focus:border-emerald-500"
                  required
                />
              </div>

              {/* Website URL */}
              <div>
                <label className="block text-zinc-400 mb-1 font-medium">Sayt Manzili (Website URL)</label>
                <input
                  type="url"
                  value={formWebsiteUrl}
                  onChange={(e) => setFormWebsiteUrl(e.target.value)}
                  placeholder="https://kun.uz"
                  className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-xl text-white text-xs focus:outline-none focus:border-emerald-500"
                />
              </div>

              {/* Feed URL with Test Button */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-zinc-400 font-medium">RSS / Atom / JSON Feed URL</label>
                  <button
                    type="button"
                    onClick={() => handleTestFeed()}
                    disabled={testingFeed || !formFeedUrl.trim()}
                    className="text-[11px] text-amber-400 hover:text-amber-300 font-medium flex items-center gap-1 disabled:opacity-50"
                  >
                    {testingFeed ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                    <span>Test Feed (Tekshirish)</span>
                  </button>
                </div>
                <input
                  type="url"
                  value={formFeedUrl}
                  onChange={(e) => setFormFeedUrl(e.target.value)}
                  placeholder="https://kun.uz/rss"
                  className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-xl text-white text-xs focus:outline-none focus:border-emerald-500 font-mono"
                  required
                />
              </div>

              {/* Test Feed Results Card */}
              {testingFeed && (
                <div className="p-3 bg-zinc-900/80 border border-zinc-800 rounded-xl flex items-center gap-2 text-zinc-400">
                  <Loader2 className="w-4 h-4 animate-spin text-amber-400" />
                  <span>Feed tekshirilmoqda va tahlil qilinmoqda...</span>
                </div>
              )}

              {testError && (
                <div className="p-3 bg-red-950/40 border border-red-900/60 rounded-xl text-red-300 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                  <span>{testError}</span>
                </div>
              )}

              {testResult && testResult.status === 'ok' && (
                <div className="p-3.5 bg-emerald-950/30 border border-emerald-900/60 rounded-xl space-y-2 text-xs">
                  <div className="flex items-center justify-between font-semibold text-emerald-400">
                    <span className="flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Feed muvaffaqiyatli tekshirildi (200 OK)</span>
                    </span>
                    <span className="px-2 py-0.5 rounded bg-emerald-900/50 text-[10px] font-mono">
                      {testResult.format}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-[11px] pt-1">
                    <div>
                      <span className="text-zinc-500 block">Maqolalar soni:</span>
                      <span className="text-white font-mono">{testResult.items_count} ta</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 block">Rasmlar holati:</span>
                      <span className={testResult.has_image ? 'text-emerald-400' : 'text-zinc-400'}>
                        {testResult.has_image ? 'Rasmlar topildi ✅' : 'Matnli'}
                      </span>
                    </div>
                  </div>

                  {testResult.latest_title && (
                    <div className="pt-1.5 border-t border-emerald-900/40">
                      <span className="text-zinc-500 block text-[10px]">Oxirgi yangilik sarlavhasi:</span>
                      <span className="text-zinc-200 line-clamp-1 font-medium">{testResult.latest_title}</span>
                      {testResult.latest_pub_date && (
                        <span className="text-zinc-500 text-[10px] block font-mono mt-0.5">
                          {testResult.latest_pub_date}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Preview Items */}
                  {testResult.preview_items && testResult.preview_items.length > 0 && (
                    <div className="pt-2 border-t border-emerald-900/40 space-y-1">
                      <span className="text-zinc-400 font-semibold block text-[10px]">Topilgan namunalar:</span>
                      {testResult.preview_items.slice(0, 2).map((item, idx) => (
                        <div key={idx} className="bg-black/30 p-1.5 rounded text-[10px] text-zinc-300">
                          <span className="font-medium block truncate">{item.title}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Options: Language & Feed Type */}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-zinc-400 mb-1 font-medium">Til</label>
                  <select
                    value={formLanguage}
                    onChange={(e) => setFormLanguage(e.target.value)}
                    className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-xl text-white text-xs focus:outline-none focus:border-emerald-500"
                  >
                    <option value="uz">O‘zbekcha (uz)</option>
                    <option value="ru">Ruscha (ru)</option>
                    <option value="en">Inglizcha (en)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-zinc-400 mb-1 font-medium">Feed Turi</label>
                  <select
                    value={formType}
                    onChange={(e) => setFormType(e.target.value)}
                    className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-xl text-white text-xs focus:outline-none focus:border-emerald-500"
                  >
                    <option value="rss">RSS 2.0</option>
                    <option value="atom">Atom Feed</option>
                    <option value="json">JSON Feed</option>
                  </select>
                </div>
              </div>

              {/* Active Toggle Switch */}
              <div className="flex items-center justify-between p-3 bg-zinc-900 border border-zinc-800 rounded-xl">
                <div>
                  <span className="text-white font-medium block">Manba holati (Active)</span>
                  <span className="text-zinc-500 text-[11px]">Faol bo‘lsa yangiliklar avtomatik yig‘iladi</span>
                </div>
                <input
                  type="checkbox"
                  checked={formActive}
                  onChange={(e) => setFormActive(e.target.checked)}
                  className="w-4 h-4 accent-emerald-500 cursor-pointer"
                />
              </div>

              {/* Action Submit */}
              <button
                type="submit"
                disabled={savingSource}
                className="w-full py-2.5 mt-2 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-50 shadow-sm"
              >
                {savingSource ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4 stroke-[2.5]" />}
                <span>{editingSource ? 'O‘zgarishlarni Saqlash' : 'Manbani Qo‘shish'}</span>
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Modal 2: Category Management Modal */}
      {showCategoryModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-t-3xl sm:rounded-2xl w-full max-w-md p-5 shadow-2xl animate-in slide-in-from-bottom duration-200">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Folder className="w-4 h-4 text-emerald-400" />
                <span>{editingCategory ? 'Kategoriyani Tahrirlash' : 'Yangi Kategoriya Yaratish'}</span>
              </h3>
              <button
                onClick={() => setShowCategoryModal(false)}
                className="p-1.5 text-zinc-400 hover:text-white rounded-xl bg-zinc-900"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveCategory} className="space-y-3.5 text-xs pt-3">
              <div className="grid grid-cols-4 gap-2">
                <div className="col-span-1">
                  <label className="block text-zinc-400 mb-1 font-medium">Icon / Emoji</label>
                  <input
                    type="text"
                    value={catIcon}
                    onChange={(e) => setCatIcon(e.target.value)}
                    placeholder="🇺🇿"
                    className="w-full text-center px-2 py-2 bg-zinc-900 border border-zinc-700 rounded-xl text-white text-base focus:outline-none focus:border-emerald-500"
                    maxLength={4}
                  />
                </div>
                <div className="col-span-3">
                  <label className="block text-zinc-400 mb-1 font-medium">Kategoriya Nomi</label>
                  <input
                    type="text"
                    value={catName}
                    onChange={(e) => setCatName(e.target.value)}
                    placeholder="Masalan: O‘zbekiston, Jahon..."
                    className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-xl text-white text-xs focus:outline-none focus:border-emerald-500"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-zinc-400 mb-1 font-medium">Tavsif (ixtiyoriy)</label>
                <input
                  type="text"
                  value={catDesc}
                  onChange={(e) => setCatDesc(e.target.value)}
                  placeholder="Kategoriya haqida qisqacha ma‘lumot"
                  className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-xl text-white text-xs focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-zinc-400 mb-1 font-medium">Tartib raqami (Sort Order)</label>
                <input
                  type="number"
                  value={catSortOrder}
                  onChange={(e) => setCatSortOrder(parseInt(e.target.value, 10) || 0)}
                  className="w-24 px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-xl text-white text-xs focus:outline-none focus:border-emerald-500"
                />
              </div>

              <button
                type="submit"
                disabled={savingCategory}
                className="w-full py-2.5 mt-2 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
              >
                {savingCategory ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4 stroke-[2.5]" />}
                <span>{editingCategory ? 'Saqlash' : 'Kategoriya Yaratish'}</span>
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
