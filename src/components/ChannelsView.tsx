import React, { useState, useEffect } from 'react';
import { ChannelItem, SourceItem } from '../types';
import { api, ApiError } from '../api';
import {
  Radio,
  Search,
  CheckCircle2,
  AlertCircle,
  Clock,
  Sliders,
  Rss,
  Trash2,
  RefreshCw,
  X,
  ChevronRight,
  ShieldAlert,
  Loader2,
  Check,
  Globe,
  Sparkles,
  Link as LinkIcon,
} from 'lucide-react';

interface ChannelsViewProps {
  onRefresh: () => void;
}

export const ChannelsView: React.FC<ChannelsViewProps> = ({ onRefresh }) => {
  const [channels, setChannels] = useState<ChannelItem[]>([]);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'paused' | 'error'>('all');
  const [selectedChannel, setSelectedChannel] = useState<ChannelItem | null>(null);

  // Detail Modal Sub-Tabs
  const [activeTab, setActiveTab] = useState<'overview' | 'sources' | 'limits' | 'schedule' | 'permissions' | 'language' | 'footer' | 'premium'>('overview');
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [dailyLimit, setDailyLimit] = useState<number>(3);
  const [scheduleMode, setScheduleMode] = useState<string>('instant');
  const [scheduleTimes, setScheduleTimes] = useState<string[]>(['09:00', '14:00', '19:00']);
  const [postLanguage, setPostLanguage] = useState<string>('uz');
  const [footerType, setFooterType] = useState<string>('none');
  const [footerText, setFooterText] = useState<string>('');
  const [footerUrl, setFooterUrl] = useState<string>('');
  const [isPremiumEligible, setIsPremiumEligible] = useState<boolean>(false);
  const [saving, setSaving] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [chRes, srcRes] = await Promise.all([
        api.getChannels({ search, status: statusFilter }),
        api.getSources(),
      ]);
      setChannels(chRes.channels || []);
      setSources(srcRes.sources || []);
    } catch (err: any) {
      setErrorMessage(err.message || 'Kanallarni yuklab bo‘lmadi');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadData();
  };

  const openChannelDetail = (channel: ChannelItem) => {
    setSelectedChannel(channel);
    setSelectedSources([...channel.selected_sources]);
    setDailyLimit(channel.daily_limit);
    setScheduleMode(channel.schedule_mode);
    setScheduleTimes([...channel.schedule_times]);
    setPostLanguage(channel.post_language || 'uz');
    setFooterType((channel as any).footer_type || 'none');
    setFooterText((channel as any).footer_text || '');
    setFooterUrl((channel as any).footer_url || '');
    setIsPremiumEligible(Boolean((channel as any).is_premium_eligible));
    setActiveTab('overview');
    setSuccessMessage(null);
    setErrorMessage(null);
    setShowDeleteConfirm(false);
  };

  const handleToggleActive = async (channel: ChannelItem) => {
    try {
      const res = await api.updateChannel(channel.chat_id, { active: !channel.active });
      setChannels((prev) =>
        prev.map((c) => (c.chat_id === channel.chat_id ? res.channel : c))
      );
      if (selectedChannel && selectedChannel.chat_id === channel.chat_id) {
        setSelectedChannel(res.channel);
      }
      onRefresh();
    } catch (err: any) {
      alert(err.message || 'Xatolik yuz berdi');
    }
  };

  const handleSaveSources = async () => {
    if (!selectedChannel) return;
    setSaving(true);
    setSuccessMessage(null);
    setErrorMessage(null);

    try {
      const res = await api.updateChannelSources(selectedChannel.chat_id, selectedSources);
      setSelectedChannel((prev) => prev ? { ...prev, selected_sources: res.selected_sources } : null);
      setChannels((prev) =>
        prev.map((c) =>
          c.chat_id === selectedChannel.chat_id
            ? { ...c, selected_sources: res.selected_sources }
            : c
        )
      );
      setSuccessMessage('Manbalar ro‘yxati muvaffaqiyatli saqlandi');
      onRefresh();
    } catch (err: any) {
      setErrorMessage(err.message || 'Manbalarni saqlab bo‘lmadi');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveLimits = async () => {
    if (!selectedChannel) return;
    setSaving(true);
    setSuccessMessage(null);
    setErrorMessage(null);

    try {
      const res = await api.updateChannel(selectedChannel.chat_id, { daily_limit: dailyLimit });
      setSelectedChannel(res.channel);
      setChannels((prev) =>
        prev.map((c) => (c.chat_id === selectedChannel.chat_id ? res.channel : c))
      );
      setSuccessMessage('Kunlik limit saqlandi');
      onRefresh();
    } catch (err: any) {
      setErrorMessage(err.message || 'Limitni saqlab bo‘lmadi');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSchedule = async () => {
    if (!selectedChannel) return;
    setSaving(true);
    setSuccessMessage(null);
    setErrorMessage(null);

    try {
      const res = await api.updateChannel(selectedChannel.chat_id, {
        schedule_mode: scheduleMode,
        schedule_times: scheduleTimes,
      });
      setSelectedChannel(res.channel);
      setChannels((prev) =>
        prev.map((c) => (c.chat_id === selectedChannel.chat_id ? res.channel : c))
      );
      setSuccessMessage('Jadval sozlamalari saqlandi');
      onRefresh();
    } catch (err: any) {
      setErrorMessage(err.message || 'Jadvalni saqlab bo‘lmadi');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveLanguage = async (newLang?: string) => {
    if (!selectedChannel) return;
    const langToSave = newLang || postLanguage;
    setSaving(true);
    setSuccessMessage(null);
    setErrorMessage(null);

    try {
      const res = await api.updateChannel(selectedChannel.chat_id, {
        post_language: langToSave,
      });
      setSelectedChannel(res.channel);
      setPostLanguage(res.channel.post_language || langToSave);
      setChannels((prev) =>
        prev.map((c) => (c.chat_id === selectedChannel.chat_id ? res.channel : c))
      );
      setSuccessMessage('Kanal post tili muvaffaqiyatli saqlandi');
      onRefresh();
    } catch (err: any) {
      setErrorMessage(err.message || 'Til sozlamasini saqlab bo‘lmadi');
    } finally {
      setSaving(false);
    }
  };

  const handleRecheckPermissions = async () => {
    if (!selectedChannel) return;
    setSaving(true);
    setSuccessMessage(null);
    setErrorMessage(null);

    try {
      const res = await api.recheckChannel(selectedChannel.chat_id);
      setSelectedChannel((prev) => prev ? { ...prev, can_post: res.can_post } : null);
      setChannels((prev) =>
        prev.map((c) =>
          c.chat_id === selectedChannel.chat_id ? { ...c, can_post: res.can_post } : c
        )
      );
      setSuccessMessage(res.message);
      onRefresh();
    } catch (err: any) {
      setErrorMessage(err.message || 'Huquqlarni tekshirib bo‘lmadi');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteChannel = async () => {
    if (!selectedChannel) return;
    setSaving(true);

    try {
      await api.deleteChannel(selectedChannel.chat_id);
      setChannels((prev) => prev.filter((c) => c.chat_id !== selectedChannel.chat_id));
      setSelectedChannel(null);
      setShowDeleteConfirm(false);
      onRefresh();
    } catch (err: any) {
      setErrorMessage(err.message || 'Kanalni o‘chirib bo‘lmadi');
      setSaving(false);
    }
  };

  const handleSaveFooter = async () => {
    if (!selectedChannel) return;
    setSaving(true);
    setSuccessMessage(null);
    setErrorMessage(null);

    try {
      const res = await api.updateChannelFooter(selectedChannel.chat_id, {
        footer_type: footerType,
        footer_text: footerText.trim() || undefined,
        footer_url: footerUrl.trim() || undefined,
      });
      setSelectedChannel(res.channel);
      setChannels((prev) =>
        prev.map((c) => (c.chat_id === selectedChannel.chat_id ? res.channel : c))
      );
      setSuccessMessage('Post oxiri (Footer) sozlamalari muvaffaqiyatli saqlandi');
      onRefresh();
    } catch (err: any) {
      setErrorMessage(err.message || 'Footerni saqlab bo‘lmadi');
    } finally {
      setSaving(false);
    }
  };

  const handleTogglePremiumEligibility = async (eligible: boolean) => {
    if (!selectedChannel) return;
    setSaving(true);
    setSuccessMessage(null);
    setErrorMessage(null);

    try {
      const res = await api.updateChannelPremiumEligibility(selectedChannel.chat_id, eligible);
      setSelectedChannel(res.channel);
      setIsPremiumEligible(eligible);
      setChannels((prev) =>
        prev.map((c) => (c.chat_id === selectedChannel.chat_id ? res.channel : c))
      );
      setSuccessMessage(
        eligible
          ? 'Kanalga Premium Kontent huquqi berildi! Endi kanal egasi uni yoqishi mumkin.'
          : 'Premium huquqi bekor qilindi.'
      );
      onRefresh();
    } catch (err: any) {
      setErrorMessage(err.message || 'Premium huquqini o‘zgartirib bo‘lmadi');
    } finally {
      setSaving(false);
    }
  };

  const toggleSourceSelection = (sourceId: string) => {
    setSelectedSources((prev) =>
      prev.includes(sourceId) ? prev.filter((id) => id !== sourceId) : [...prev, sourceId]
    );
  };

  const selectAllSources = () => {
    setSelectedSources(sources.map((s) => s.id));
  };

  const deselectAllSources = () => {
    setSelectedSources([]);
  };

  return (
    <div className="space-y-4 pb-20">
      {/* Header & Search */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <Radio className="w-5 h-5 text-emerald-400" />
            <span>Kanallarni Boshqarish</span>
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Jami {channels.length} ta Telegram kanal ulangan
          </p>
        </div>

        {/* Search Bar */}
        <form onSubmit={handleSearchSubmit} className="relative w-full sm:w-64">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Nomi, ID yoki username..."
            className="w-full pl-8 pr-3 py-2 bg-zinc-900 border border-zinc-800 rounded-xl text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500"
          />
          <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-2.5" />
        </form>
      </div>

      {/* Segmented Status Filter */}
      <div className="flex items-center gap-1.5 p-1 bg-zinc-900/90 border border-zinc-800 rounded-xl overflow-x-auto">
        {(
          [
            { id: 'all', label: 'Barchasi' },
            { id: 'active', label: 'Faol' },
            { id: 'paused', label: 'To‘xtatilgan' },
            { id: 'error', label: 'Xatolar' },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setStatusFilter(tab.id)}
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

      {/* Channel Cards List */}
      {loading ? (
        <div className="py-16 text-center text-zinc-500 flex flex-col items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-emerald-500 mb-2" />
          <span className="text-xs">Kanallar yuklanmoqda...</span>
        </div>
      ) : channels.length === 0 ? (
        <div className="py-12 bg-zinc-900/40 border border-zinc-800/80 rounded-2xl text-center text-zinc-500 text-xs p-6">
          <Radio className="w-8 h-8 mx-auto text-zinc-600 mb-2" />
          <span>Hech qanday kanal topilmadi</span>
        </div>
      ) : (
        <div className="space-y-3">
          {channels.map((channel) => {
            const hasError = !channel.can_post;
            const isPaused = !channel.active;

            return (
              <div
                key={channel.chat_id}
                className="bg-zinc-900/90 border border-zinc-800 hover:border-zinc-700/80 rounded-2xl p-4 transition-all"
              >
                {/* Top Row: Title, Plan, Status */}
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-sm font-semibold text-white truncate">
                        {channel.title}
                      </h3>
                      {channel.username && (
                        <span className="text-xs text-zinc-400 font-mono">
                          @{channel.username}
                        </span>
                      )}
                      <span
                        className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border ${
                          channel.plan === 'contract'
                            ? 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30'
                            : 'bg-zinc-800 text-zinc-400 border-zinc-700'
                        }`}
                      >
                        {channel.plan}
                      </span>
                      <span className="text-[10px] font-medium px-1.5 py-0.5 rounded border bg-blue-500/10 text-blue-300 border-blue-500/30 flex items-center gap-1">
                        <Globe className="w-2.5 h-2.5" />
                        <span>
                          {channel.post_language === 'uz_cyrl'
                            ? '🇺🇿 UZ (Kirill)'
                            : channel.post_language === 'ru'
                            ? '🇷🇺 RU'
                            : channel.post_language === 'en'
                            ? '🇬🇧 EN'
                            : channel.post_language === 'auto'
                            ? '🔄 Auto'
                            : '🇺🇿 UZ'}
                        </span>
                      </span>
                      {Boolean((channel as any).is_premium_eligible) && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded border bg-amber-500/10 text-amber-300 border-amber-500/30 flex items-center gap-1">
                          <Sparkles className="w-2.5 h-2.5 text-amber-400" />
                          <span>Premium</span>
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-3 text-[11px] text-zinc-500 mt-1 font-mono">
                      <span>ID: {channel.chat_id}</span>
                      <span>Egasi: {channel.owner_user_id}</span>
                    </div>
                  </div>

                  {/* Status Badges */}
                  <div className="flex items-center gap-2 shrink-0">
                    {hasError ? (
                      <span className="flex items-center gap-1 text-[11px] font-medium text-red-400 bg-red-950/40 border border-red-900/60 px-2 py-0.5 rounded-full">
                        <ShieldAlert className="w-3 h-3" />
                        <span>Ruxsat yo‘q</span>
                      </span>
                    ) : isPaused ? (
                      <span className="text-[11px] font-medium text-amber-400 bg-amber-950/40 border border-amber-900/60 px-2 py-0.5 rounded-full">
                        To‘xtatilgan
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-950/40 border border-emerald-900/60 px-2 py-0.5 rounded-full">
                        <CheckCircle2 className="w-3 h-3" />
                        <span>Faol</span>
                      </span>
                    )}
                  </div>
                </div>

                {/* Progress / Delivery Metrics */}
                <div className="mt-3.5 pt-3 border-t border-zinc-800/80 grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="bg-zinc-950/50 rounded-xl p-2">
                    <span className="text-[10px] text-zinc-500 block mb-0.5">Bugun / Limit</span>
                    <span className="font-bold text-zinc-200">
                      {channel.today_delivered_count} / {channel.daily_limit}
                    </span>
                  </div>

                  <div className="bg-zinc-950/50 rounded-xl p-2">
                    <span className="text-[10px] text-zinc-500 block mb-0.5">Jami Yetkazilgan</span>
                    <span className="font-bold text-emerald-400">
                      {channel.total_delivered_count} ta
                    </span>
                  </div>

                  <div className="bg-zinc-950/50 rounded-xl p-2">
                    <span className="text-[10px] text-zinc-500 block mb-0.5">Manbalar</span>
                    <span className="font-bold text-zinc-200">
                      {channel.selected_sources?.length || 0} ta
                    </span>
                  </div>
                </div>

                {/* Actions Row */}
                <div className="mt-3 flex items-center justify-between gap-2">
                  <button
                    onClick={() => handleToggleActive(channel)}
                    className={`text-xs px-3 py-1.5 rounded-xl border font-medium transition-colors ${
                      channel.active
                        ? 'bg-zinc-800 border-zinc-700 text-zinc-300 hover:text-amber-300'
                        : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20'
                    }`}
                  >
                    {channel.active ? 'To‘xtatish' : 'Faollashtirish'}
                  </button>

                  <button
                    onClick={() => openChannelDetail(channel)}
                    className="text-xs px-3.5 py-1.5 bg-zinc-900 border border-zinc-700 hover:border-zinc-600 text-white rounded-xl font-medium flex items-center gap-1 transition-colors"
                  >
                    <span>Boshqarish</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Channel Detail Modal / Drawer */}
      {selectedChannel && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-t-3xl sm:rounded-2xl w-full max-w-lg max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-in slide-in-from-bottom duration-200">
            {/* Modal Header */}
            <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white truncate max-w-[280px]">
                  {selectedChannel.title}
                </h3>
                <span className="text-[11px] text-zinc-400 font-mono">
                  Chat ID: {selectedChannel.chat_id}
                </span>
              </div>
              <button
                onClick={() => setSelectedChannel(null)}
                className="p-1.5 text-zinc-400 hover:text-white rounded-xl bg-zinc-900 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Tabs */}
            <div className="flex border-b border-zinc-800/80 px-3 bg-zinc-900/50 overflow-x-auto">
              {(
                [
                  { id: 'overview', label: 'Umumiy' },
                  { id: 'sources', label: `Manbalar (${selectedSources.length})` },
                  { id: 'language', label: 'Post Tili' },
                  { id: 'footer', label: 'Footer' },
                  { id: 'premium', label: 'Premium' },
                  { id: 'limits', label: 'Limit' },
                  { id: 'schedule', label: 'Jadval' },
                  { id: 'permissions', label: 'Huquqlar' },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`py-2.5 px-3 text-xs font-medium border-b-2 whitespace-nowrap transition-colors ${
                    activeTab === tab.id
                      ? 'border-emerald-500 text-emerald-400'
                      : 'border-transparent text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Modal Feedback */}
            {successMessage && (
              <div className="mx-4 mt-3 p-2.5 bg-emerald-950/40 border border-emerald-900/60 rounded-xl text-xs text-emerald-300 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{successMessage}</span>
              </div>
            )}
            {errorMessage && (
              <div className="mx-4 mt-3 p-2.5 bg-red-950/40 border border-red-900/60 rounded-xl text-xs text-red-300 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            {/* Modal Body */}
            <div className="p-4 overflow-y-auto flex-1 space-y-4 text-xs">
              {/* 1. OVERVIEW TAB */}
              {activeTab === 'overview' && (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-zinc-900 p-3 rounded-xl">
                      <span className="text-zinc-500 block mb-1">Tarif</span>
                      <span className="font-semibold text-white uppercase">
                        {selectedChannel.plan}
                      </span>
                    </div>
                    <div className="bg-zinc-900 p-3 rounded-xl">
                      <span className="text-zinc-500 block mb-1">Holati</span>
                      <span className="font-semibold text-white">
                        {selectedChannel.active ? 'Faol' : 'To‘xtatilgan'}
                      </span>
                    </div>
                    <div className="bg-zinc-900 p-3 rounded-xl">
                      <span className="text-zinc-500 block mb-1">Kunlik limit</span>
                      <span className="font-semibold text-white">
                        {selectedChannel.daily_limit} ta post
                      </span>
                    </div>
                    <div className="bg-zinc-900 p-3 rounded-xl">
                      <span className="text-zinc-500 block mb-1">Yetkazish rejimi</span>
                      <span className="font-semibold text-white capitalize">
                        {selectedChannel.schedule_mode}
                      </span>
                    </div>
                    <div className="bg-zinc-900 p-3 rounded-xl">
                      <span className="text-zinc-500 block mb-1">Post Tili</span>
                      <span className="font-semibold text-blue-300 flex items-center gap-1.5">
                        <Globe className="w-3.5 h-3.5" />
                        <span>
                          {selectedChannel.post_language === 'uz_cyrl'
                            ? '🇺🇿 O‘zbekcha — Kirill'
                            : selectedChannel.post_language === 'ru'
                            ? '🇷🇺 Русский'
                            : selectedChannel.post_language === 'en'
                            ? '🇬🇧 English'
                            : selectedChannel.post_language === 'auto'
                            ? '🔄 Avtomatik'
                            : '🇺🇿 O‘zbekcha'}
                        </span>
                      </span>
                    </div>
                    <div className="bg-zinc-900 p-3 rounded-xl">
                      <span className="text-zinc-500 block mb-1">Premium Kontent</span>
                      <span className={`font-semibold flex items-center gap-1.5 ${
                        selectedChannel.is_premium_eligible ? 'text-amber-300' : 'text-zinc-500'
                      }`}>
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>
                          {selectedChannel.is_premium_eligible
                            ? (selectedChannel.premium_enabled ? 'Yoqilgan (Faol)' : 'Huquq bor (Kutmoqda)')
                            : 'Huquq berilmagan'}
                        </span>
                      </span>
                    </div>
                    <div className="bg-zinc-900 p-3 rounded-xl">
                      <span className="text-zinc-500 block mb-1">Post Footer</span>
                      <span className="font-semibold text-zinc-300 capitalize">
                        {selectedChannel.footer_type && selectedChannel.footer_type !== 'none'
                          ? `${selectedChannel.footer_type} rejimida`
                          : 'O‘chirilgan'}
                      </span>
                    </div>
                  </div>

                  <div className="bg-zinc-900 p-3 rounded-xl space-y-1.5">
                    <div className="flex justify-between text-zinc-400">
                      <span>Telegram Chat ID:</span>
                      <span className="font-mono text-white">{selectedChannel.chat_id}</span>
                    </div>
                    <div className="flex justify-between text-zinc-400">
                      <span>Kanal Egasi ID:</span>
                      <span className="font-mono text-white">{selectedChannel.owner_user_id}</span>
                    </div>
                    <div className="flex justify-between text-zinc-400">
                      <span>Uланган sana:</span>
                      <span className="text-white">
                        {new Date(selectedChannel.created_at).toLocaleDateString('uz-UZ')}
                      </span>
                    </div>
                    <div className="flex justify-between text-zinc-400">
                      <span>So‘nggi yetkazilgan:</span>
                      <span className="text-white">
                        {selectedChannel.last_delivered_at
                          ? new Date(selectedChannel.last_delivered_at).toLocaleTimeString('uz-UZ')
                          : 'Hali xabar yetkazilmagan'}
                      </span>
                    </div>
                  </div>

                  {/* Disconnect Channel Section */}
                  <div className="pt-2 border-t border-zinc-800">
                    {!showDeleteConfirm ? (
                      <button
                        onClick={() => setShowDeleteConfirm(true)}
                        className="w-full py-2.5 px-3 bg-red-950/20 hover:bg-red-950/40 border border-red-900/40 text-red-400 rounded-xl font-medium flex items-center justify-center gap-1.5 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                        <span>Kanalni Tizimdan Uzish</span>
                      </button>
                    ) : (
                      <div className="p-3 bg-red-950/30 border border-red-900/60 rounded-xl space-y-2">
                        <p className="text-red-200 font-medium">
                          Haqiqatan ham bu kanalni uzmoqchimisiz? Bot yangiliklar yuborishni to‘xtatadi.
                        </p>
                        <div className="flex gap-2">
                          <button
                            onClick={handleDeleteChannel}
                            disabled={saving}
                            className="flex-1 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg font-semibold"
                          >
                            {saving ? 'O‘chirilmoqda...' : 'Ha, Uzish'}
                          </button>
                          <button
                            onClick={() => setShowDeleteConfirm(false)}
                            className="px-4 py-2 bg-zinc-800 text-zinc-300 rounded-lg"
                          >
                            Bekor qilish
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* 2. SOURCES TAB */}
              {activeTab === 'sources' && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-zinc-400">
                      Kanal qaysi RSS manbalardan yangilik olsin?
                    </span>
                    <div className="flex gap-2">
                      <button
                        onClick={selectAllSources}
                        className="text-[11px] text-emerald-400 hover:underline"
                      >
                        Barchasi
                      </button>
                      <span className="text-zinc-600">|</span>
                      <button
                        onClick={deselectAllSources}
                        className="text-[11px] text-zinc-400 hover:underline"
                      >
                        Tozalash
                      </button>
                    </div>
                  </div>

                  <div className="space-y-1.5 max-h-60 overflow-y-auto pr-1">
                    {sources.map((src) => {
                      const isSelected = selectedSources.includes(src.id);
                      return (
                        <div
                          key={src.id}
                          onClick={() => toggleSourceSelection(src.id)}
                          className={`p-2.5 rounded-xl border flex items-center justify-between cursor-pointer transition-colors ${
                            isSelected
                              ? 'bg-emerald-500/10 border-emerald-500/40 text-white'
                              : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:border-zinc-700'
                          }`}
                        >
                          <div className="flex items-center gap-2.5">
                            <div
                              className={`w-4 h-4 rounded flex items-center justify-center border ${
                                isSelected
                                  ? 'bg-emerald-500 border-emerald-500 text-zinc-950'
                                  : 'border-zinc-700'
                              }`}
                            >
                              {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
                            </div>
                            <div>
                              <span className="font-semibold block">{src.name}</span>
                              <span className="text-[10px] text-zinc-500">{src.category}</span>
                            </div>
                          </div>
                          <span className="text-[10px] text-zinc-500 font-mono">
                            {src.type}
                          </span>
                        </div>
                      );
                    })}
                  </div>

                  <button
                    onClick={handleSaveSources}
                    disabled={saving}
                    className="w-full py-2.5 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                  >
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                    <span>Manbalarni Saqlash</span>
                  </button>
                </div>
              )}

              {/* POST LANGUAGE TAB */}
              {activeTab === 'language' && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-zinc-300 font-semibold mb-1 text-xs">
                      Telegram Kanal Post Tili
                    </label>
                    <p className="text-[11px] text-zinc-400 mb-3">
                      Ushbu kanalga yuboriladigan barcha yangiliklar tanlangan tilga Gemini AI orqali avtomatik tarjima qilinadi.
                    </p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      {[
                        {
                          id: 'uz',
                          name: '🇺🇿 O‘zbekcha',
                          desc: 'O‘zbek tilidagi sarlavha va qisqacha mazmun (standart)',
                        },
                        {
                          id: 'uz_cyrl',
                          name: '🇺🇿 O‘zbekcha — Kirill',
                          desc: 'O‘zbek kirill yozuvidagi sarlavha va qisqacha mazmun',
                        },
                        {
                          id: 'ru',
                          name: '🇷🇺 Русский',
                          desc: 'Русский перевод заголовка и краткого описания',
                        },
                        {
                          id: 'en',
                          name: '🇬🇧 English',
                          desc: 'English title and summary translation',
                        },
                        {
                          id: 'auto',
                          name: '🔄 Asl til',
                          desc: 'Asl tilda qoldirish (tarjima qilinmaydi)',
                        },
                      ].map((item) => {
                        const isSelected = postLanguage === item.id;
                        return (
                          <div
                            key={item.id}
                            onClick={() => setPostLanguage(item.id)}
                            className={`p-3 rounded-xl border cursor-pointer transition-all ${
                              isSelected
                                ? 'bg-emerald-500/10 border-emerald-500 text-white shadow-sm ring-1 ring-emerald-500/40'
                                : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:border-zinc-700'
                            }`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className="font-semibold text-xs text-white">
                                {item.name}
                              </span>
                              <div
                                className={`w-4 h-4 rounded-full flex items-center justify-center border ${
                                  isSelected
                                    ? 'bg-emerald-500 border-emerald-500 text-zinc-950'
                                    : 'border-zinc-700'
                                }`}
                              >
                                {isSelected && <Check className="w-2.5 h-2.5 stroke-[3]" />}
                              </div>
                            </div>
                            <p className="text-[10px] text-zinc-400 leading-snug">
                              {item.desc}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  <div className="p-3 bg-zinc-900/70 border border-zinc-800/80 rounded-xl space-y-1">
                    <span className="text-[11px] font-semibold text-zinc-300 block">
                      ⚡ Qanday ishlaydi?
                    </span>
                    <p className="text-[10px] text-zinc-400 leading-relaxed">
                      1. Xorijiy (NPR, Guardian, Al Jazeera va h.k.) manbalardan yangilik kelganda Gemini AI orqali real vaqt rejimida tarjima qilinadi.<br />
                      2. API sarfini tejash uchun tarjimalar keshlanadi.<br />
                      3. Har bir kanal alohida tilga sozlangan bo‘lishi mumkin.
                    </p>
                  </div>

                  <button
                    onClick={() => handleSaveLanguage(postLanguage)}
                    disabled={saving}
                    className="w-full py-2.5 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                  >
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                    <span>Tilni Saqlash</span>
                  </button>
                </div>
              )}

              {/* 3. LIMITS TAB */}
              {activeTab === 'limits' && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-zinc-400 mb-1.5 font-medium">
                      Kunlik Post Limiti
                    </label>
                    <div className="flex items-center gap-3">
                      <input
                        type="number"
                        min="1"
                        max={selectedChannel.plan === 'contract' ? 100 : 3}
                        value={dailyLimit}
                        onChange={(e) => setDailyLimit(parseInt(e.target.value, 10) || 1)}
                        className="w-24 px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-xl text-white font-mono text-sm focus:outline-none focus:border-emerald-500"
                      />
                      <span className="text-zinc-400">post / kun</span>
                    </div>

                    {selectedChannel.plan === 'free' ? (
                      <p className="text-[11px] text-amber-400 mt-2">
                        Free tarifdagi kanallar uchun maksimal limit — 3 ta post.
                        Ko‘proq limit berish uchun kanal egasiga <strong>Contract</strong> tarifini biriktiring.
                      </p>
                    ) : (
                      <p className="text-[11px] text-indigo-300 mt-2">
                        Contract tarifi faol: istalgan limit belgilashingiz mumkin.
                      </p>
                    )}
                  </div>

                  <button
                    onClick={handleSaveLimits}
                    disabled={saving}
                    className="w-full py-2.5 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                  >
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                    <span>Limitni Saqlash</span>
                  </button>
                </div>
              )}

              {/* FOOTER TAB */}
              {activeTab === 'footer' && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-zinc-400 font-medium mb-1.5">
                      Post Oxiri (Footer) Turi
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        { id: 'none', label: '❌ O‘chirilgan', desc: 'Footer qo‘shilmaydi' },
                        { id: 'text', label: '📝 Oddiy matn', desc: '@kanalingiz obuna bo‘ling' },
                        { id: 'link', label: '🔗 Matnli havola', desc: 'Batafsil ma’lumot' },
                        { id: 'button', label: '🔘 Inline tugma', desc: 'Post ostida tugma' },
                      ].map((f) => (
                        <button
                          key={f.id}
                          type="button"
                          onClick={() => setFooterType(f.id)}
                          className={`p-3 rounded-xl border text-left transition-colors ${
                            footerType === f.id
                              ? 'bg-emerald-500/10 border-emerald-500 text-white'
                              : 'bg-zinc-900 border-zinc-800 text-zinc-400'
                          }`}
                        >
                          <span className="font-bold block text-xs">{f.label}</span>
                          <span className="text-[10px] text-zinc-500">{f.desc}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {footerType !== 'none' && (
                    <div className="space-y-3 pt-2 border-t border-zinc-800">
                      <div>
                        <label className="block text-zinc-400 font-medium mb-1">
                          {footerType === 'button' ? 'Tugma matni' : 'Footer matni'} *
                        </label>
                        <input
                          type="text"
                          value={footerText}
                          onChange={(e) => setFooterText(e.target.value)}
                          placeholder={footerType === 'button' ? 'Obuna bo‘lish 🚀' : 'Bizning kanal: @kanalingiz'}
                          className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-xl text-white text-xs focus:outline-none focus:border-emerald-500"
                        />
                      </div>

                      {(footerType === 'link' || footerType === 'button') && (
                        <div>
                          <label className="block text-zinc-400 font-medium mb-1">
                            Havola (URL) *
                          </label>
                          <input
                            type="text"
                            value={footerUrl}
                            onChange={(e) => setFooterUrl(e.target.value)}
                            placeholder="https://t.me/kanalingiz"
                            className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-xl text-white text-xs focus:outline-none focus:border-emerald-500 font-mono"
                          />
                        </div>
                      )}
                    </div>
                  )}

                  <button
                    onClick={handleSaveFooter}
                    disabled={saving}
                    className="w-full py-2.5 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                  >
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                    <span>Footerni Saqlash</span>
                  </button>
                </div>
              )}

              {/* PREMIUM TAB */}
              {activeTab === 'premium' && (
                <div className="space-y-4">
                  <div className="p-3.5 bg-amber-500/10 border border-amber-500/20 rounded-xl">
                    <div className="flex items-start gap-3">
                      <Sparkles className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                      <div>
                        <h4 className="font-semibold text-white text-xs">Premium Kontent Huquqi</h4>
                        <p className="text-[11px] text-zinc-400 mt-0.5 leading-relaxed">
                          Markaziy "Postlar" kanalidan keladigan qo‘lda tayyorlangan eksklyuziv postlarni ushbu kanalga yetkazish huquqi.
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="bg-zinc-900 p-3.5 rounded-xl border border-zinc-800 space-y-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="font-bold text-white block text-xs">Super Admin Huquqi (Eligibility)</span>
                        <span className="text-[10px] text-zinc-400">
                          {isPremiumEligible ? 'Ushbu kanal Premium olish huquqiga ega' : 'Huquq berilmagan'}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleTogglePremiumEligibility(!isPremiumEligible)}
                        disabled={saving}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                          isPremiumEligible
                            ? 'bg-amber-500 text-zinc-950 hover:bg-amber-400'
                            : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
                        }`}
                      >
                        {isPremiumEligible ? '🟢 Huquq Faol' : '⚪ Huquq Berish'}
                      </button>
                    </div>

                    <div className="pt-2 border-t border-zinc-800 text-[11px] text-zinc-400">
                      <span>Kanal egasi holati: </span>
                      <strong className="text-white">
                        {Boolean((selectedChannel as any).premium_enabled) ? 'Yoqilgan (ON)' : 'O‘chirilgan (OFF)'}
                      </strong>
                    </div>
                  </div>
                </div>
              )}

              {/* 4. SCHEDULE TAB */}
              {activeTab === 'schedule' && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-zinc-400 mb-1.5 font-medium">
                      Yetkazish Rejimi (Mode)
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => setScheduleMode('instant')}
                        className={`p-3 rounded-xl border text-left transition-colors ${
                          scheduleMode === 'instant'
                            ? 'bg-emerald-500/10 border-emerald-500 text-white'
                            : 'bg-zinc-900 border-zinc-800 text-zinc-400'
                        }`}
                      >
                        <span className="font-bold block text-xs">⚡ Instant (Darhol)</span>
                        <span className="text-[10px] text-zinc-500">
                          Manbada yangilik chiqishi bilan
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setScheduleMode('custom')}
                        className={`p-3 rounded-xl border text-left transition-colors ${
                          scheduleMode === 'custom' || scheduleMode === 'scheduled' || scheduleMode === 'batch'
                            ? 'bg-emerald-500/10 border-emerald-500 text-white'
                            : 'bg-zinc-900 border-zinc-800 text-zinc-400'
                        }`}
                      >
                        <span className="font-bold block text-xs">🕐 Custom (Belgilangan)</span>
                        <span className="text-[10px] text-zinc-500">
                          Kunlik belgilangan soatlarda
                        </span>
                      </button>
                    </div>
                  </div>

                  {(scheduleMode === 'custom' || scheduleMode === 'scheduled' || scheduleMode === 'batch') && (
                    <div className="space-y-2.5">
                      <div className="flex items-center justify-between">
                        <label className="block text-zinc-400 font-medium">
                          Post Vaqtlari (Asia/Tashkent)
                        </label>
                        <span className="text-[10px] text-zinc-500">
                          Maksimal: {selectedChannel.plan === 'contract' ? selectedChannel.daily_limit : 3} ta slot
                        </span>
                      </div>

                      {/* Custom times input text */}
                      <input
                        type="text"
                        value={scheduleTimes.join(', ')}
                        onChange={(e) => {
                          const parts = e.target.value
                            .split(',')
                            .map((s) => s.trim())
                            .filter(Boolean);
                          setScheduleTimes(parts);
                        }}
                        placeholder="09:00, 14:00, 19:00"
                        className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-xl text-white font-mono text-xs focus:outline-none focus:border-emerald-500"
                      />

                      {/* Quick Presets */}
                      <div className="flex items-center gap-2 pt-1">
                        <span className="text-[10px] text-zinc-500">Shablonlar:</span>
                        <button
                          type="button"
                          onClick={() => setScheduleTimes(['09:00', '14:00', '19:00'])}
                          className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded text-[10px] font-mono"
                        >
                          09:00, 14:00, 19:00
                        </button>
                        <button
                          type="button"
                          onClick={() => setScheduleTimes(['08:30', '13:00', '18:30'])}
                          className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded text-[10px] font-mono"
                        >
                          08:30, 13:00, 18:30
                        </button>
                      </div>
                    </div>
                  )}

                  <button
                    onClick={handleSaveSchedule}
                    disabled={saving}
                    className="w-full py-2.5 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                  >
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                    <span>Jadvalni Saqlash</span>
                  </button>
                </div>
              )}

              {/* 5. PERMISSIONS TAB */}
              {activeTab === 'permissions' && (
                <div className="space-y-4">
                  <div
                    className={`p-3.5 rounded-xl border flex items-start gap-3 ${
                      selectedChannel.can_post
                        ? 'bg-emerald-950/20 border-emerald-900/40 text-emerald-300'
                        : 'bg-red-950/30 border-red-900/60 text-red-300'
                    }`}
                  >
                    {selectedChannel.can_post ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                    ) : (
                      <ShieldAlert className="w-5 h-5 text-red-400 shrink-0" />
                    )}
                    <div>
                      <span className="font-bold block text-xs">
                        {selectedChannel.can_post
                          ? 'Botda xabar yozish ruxsati bor'
                          : 'Bot ruxsati yetarli emas!'}
                      </span>
                      <p className="text-[11px] opacity-90 mt-0.5">
                        {selectedChannel.can_post
                          ? 'Bot ushbu kanalda administrator va "Post Messages" huquqiga ega.'
                          : 'Botni Telegram kanalingizga Administrator sifatida qo‘shing va xabar yozish ruxsatini yoqing.'}
                      </p>
                    </div>
                  </div>

                  <button
                    onClick={handleRecheckPermissions}
                    disabled={saving}
                    className="w-full py-2.5 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-white font-semibold rounded-xl flex items-center justify-center gap-2 transition-colors"
                  >
                    <RefreshCw className={`w-4 h-4 ${saving ? 'animate-spin' : ''}`} />
                    <span>Huquqlarni Qayta Tekshirish</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
