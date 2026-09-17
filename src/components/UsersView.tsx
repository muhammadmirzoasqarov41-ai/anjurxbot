import React, { useState, useEffect, useRef } from 'react';
import { UserItem } from '../types';
import { api } from '../api';
import {
  Users,
  Search,
  CheckCircle2,
  AlertCircle,
  X,
  ChevronRight,
  Shield,
  Loader2,
  Radio,
  UserPlus,
  BellRing,
  Sparkles,
  RefreshCw,
  Clock,
  Send,
} from 'lucide-react';

interface UsersViewProps {
  onRefresh: () => void;
}

export const UsersView: React.FC<UsersViewProps> = ({ onRefresh }) => {
  const [users, setUsers] = useState<UserItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [planFilter, setPlanFilter] = useState<'all' | 'contract' | 'free'>('all');
  const [selectedUser, setSelectedUser] = useState<UserItem | null>(null);

  // Real-time states
  const [lastSyncTime, setLastSyncTime] = useState<Date>(new Date());
  const [liveConnected, setLiveConnected] = useState(false);
  const [newUserNotification, setNewUserNotification] = useState<string | null>(null);
  const prevUsersCountRef = useRef<number | null>(null);

  // Contract form state
  const [plan, setPlan] = useState<'free' | 'contract'>('free');
  const [customLimit, setCustomLimit] = useState<number>(10);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Add User Modal state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [addUserId, setAddUserId] = useState('');
  const [addFirstName, setAddFirstName] = useState('');
  const [addUsername, setAddUsername] = useState('');
  const [addPlan, setAddPlan] = useState<'free' | 'contract'>('free');
  const [addLimit, setAddLimit] = useState(10);
  const [addingUser, setAddingUser] = useState(false);

  // Fetch users with search/filter support
  const fetchUsers = async (isBackground = false) => {
    if (!isBackground) setLoading(true);
    try {
      const res = await api.getUsers({ search, plan: planFilter });
      const incomingUsers = res.users || [];

      // Check if new users were detected
      if (prevUsersCountRef.current !== null && incomingUsers.length > prevUsersCountRef.current) {
        const diff = incomingUsers.length - prevUsersCountRef.current;
        const newest = incomingUsers[incomingUsers.length - 1];
        setNewUserNotification(
          `🔔 Yangi ${diff} ta foydalanuvchi qo‘shildi! Oxirgisi: ${newest?.first_name || 'Foydalanuvchi'} (ID: ${newest?.user_id})`
        );
        onRefresh();
      }
      prevUsersCountRef.current = incomingUsers.length;

      setUsers(incomingUsers);
      setLastSyncTime(new Date());
      setLiveConnected(true);
    } catch (err: any) {
      if (!isBackground) {
        setErrorMessage(err.message || 'Foydalanuvchilarni yuklab bo‘lmadi');
      }
    } finally {
      if (!isBackground) setLoading(false);
    }
  };

  // Initial load & filter change
  useEffect(() => {
    fetchUsers(false);
  }, [planFilter]);

  // Real-time EventSource (SSE) listener & automatic fast polling (every 3.5s)
  useEffect(() => {
    let eventSource: EventSource | null = null;
    try {
      eventSource = new EventSource('/api/events');
      eventSource.onopen = () => {
        setLiveConnected(true);
      };
      eventSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (
            payload.type === 'connected' ||
            payload.type === 'users_updated' ||
            payload.type === 'user_created' ||
            payload.type === 'database_changed'
          ) {
            setLastSyncTime(new Date());
            setLiveConnected(true);
            // Refresh users silently
            fetchUsers(true);
          }
        } catch {
          // ignore
        }
      };
      eventSource.onerror = () => {
        setLiveConnected(false);
      };
    } catch {
      setLiveConnected(false);
    }

    // Interval polling fallback so real-time updates are 100% guaranteed
    const pollInterval = setInterval(() => {
      fetchUsers(true);
    }, 3500);

    return () => {
      if (eventSource) {
        eventSource.close();
      }
      clearInterval(pollInterval);
    };
  }, [search, planFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchUsers(false);
  };

  const openUserDetail = (user: UserItem) => {
    setSelectedUser(user);
    setPlan(user.plan);
    setCustomLimit(user.custom_limit || 10);
    setMessage(null);
    setErrorMessage(null);
  };

  const handleSaveContract = async () => {
    if (!selectedUser) return;
    setSaving(true);
    setMessage(null);
    setErrorMessage(null);

    try {
      const res = await api.updateUserContract(selectedUser.user_id, plan, customLimit);
      setSelectedUser((prev) => (prev ? { ...prev, ...res.user } : null));
      setUsers((prev) =>
        prev.map((u) => (u.user_id === selectedUser.user_id ? { ...u, ...res.user } : u))
      );
      setMessage(res.message);
      onRefresh();
    } catch (err: any) {
      setErrorMessage(err.message || 'Tarifni saqlab bo‘lmadi');
    } finally {
      setSaving(false);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    const uid = parseInt(addUserId, 10);
    if (!uid || isNaN(uid)) {
      setErrorMessage('Iltimos, haqiqiy raqamli Telegram ID kiriting');
      return;
    }

    setAddingUser(true);
    setErrorMessage(null);
    try {
      const res = await api.createUser({
        user_id: uid,
        first_name: addFirstName || 'Foydalanuvchi',
        username: addUsername || undefined,
        plan: addPlan,
        custom_limit: addPlan === 'contract' ? addLimit : undefined,
      });

      setIsAddModalOpen(false);
      setAddUserId('');
      setAddFirstName('');
      setAddUsername('');
      setNewUserNotification(
        `✅ Yangi foydalanuvchi muvaffaqiyatli qo‘shildi: ID ${uid}. Super Admin ID ga bildirishnoma uzatildi!`
      );
      fetchUsers(true);
      onRefresh();
    } catch (err: any) {
      setErrorMessage(err.message || 'Foydalanuvchi qo‘shishda xatolik yuz berdi');
    } finally {
      setAddingUser(false);
    }
  };

  // Metrics calculation
  const totalCount = users.length;
  const contractCount = users.filter((u) => u.plan === 'contract').length;
  const freeCount = users.filter((u) => u.plan !== 'contract').length;

  return (
    <div className="space-y-4 pb-20">
      {/* Top Banner with Real-time indicator */}
      <div className="bg-gradient-to-r from-blue-950/40 via-zinc-900/60 to-zinc-900 border border-blue-900/40 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-center text-blue-400 shrink-0">
            <Users className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white tracking-tight">
                Foydalanuvchilar Boshqaruvi
              </h2>
              {liveConnected ? (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                  Real-time Jonli
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                  Auto-Polling
                </span>
              )}
            </div>
            <p className="text-xs text-zinc-400 flex items-center gap-1.5 mt-0.5">
              <Clock className="w-3 h-3 text-zinc-500" />
              <span>Sinxronizatsiya: {lastSyncTime.toLocaleTimeString()}</span>
              <span className="text-zinc-600">•</span>
              <span className="text-emerald-400">Super Adminga yangi user xabarnomasi faol</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => fetchUsers(false)}
            title="Yangilash"
            className="p-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 rounded-xl text-zinc-300 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-400' : ''}`} />
          </button>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 shadow-md shadow-blue-900/30 transition-all"
          >
            <UserPlus className="w-3.5 h-3.5" />
            <span>Foydalanuvchi Qo‘shish</span>
          </button>
        </div>
      </div>

      {/* Real-time New User Alert Notification Banner */}
      {newUserNotification && (
        <div className="p-3 bg-blue-950/60 border border-blue-500/40 rounded-xl text-xs text-blue-200 flex items-center justify-between gap-2 animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="flex items-center gap-2 min-w-0">
            <BellRing className="w-4 h-4 text-blue-400 shrink-0 animate-bounce" />
            <span className="font-medium truncate">{newUserNotification}</span>
          </div>
          <button
            onClick={() => setNewUserNotification(null)}
            className="p-1 text-blue-400 hover:text-white rounded-lg hover:bg-blue-900/40"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Real-time Metrics Counters */}
      <div className="grid grid-cols-3 gap-2.5">
        <div className="p-3 rounded-xl bg-zinc-900/90 border border-zinc-800">
          <span className="text-[11px] text-zinc-400 block font-medium">Jami Userlar</span>
          <div className="flex items-baseline gap-1.5 mt-0.5">
            <span className="text-xl font-bold text-white tracking-tight">{totalCount}</span>
            <span className="text-[10px] text-zinc-500">ta</span>
          </div>
        </div>
        <div className="p-3 rounded-xl bg-zinc-900/90 border border-indigo-900/40">
          <span className="text-[11px] text-indigo-300 block font-medium">Shartnoma (Contract)</span>
          <div className="flex items-baseline gap-1.5 mt-0.5">
            <span className="text-xl font-bold text-indigo-400 tracking-tight">{contractCount}</span>
            <span className="text-[10px] text-zinc-500">ta</span>
          </div>
        </div>
        <div className="p-3 rounded-xl bg-zinc-900/90 border border-zinc-800">
          <span className="text-[11px] text-zinc-400 block font-medium">Free (Bepul)</span>
          <div className="flex items-baseline gap-1.5 mt-0.5">
            <span className="text-xl font-bold text-zinc-200 tracking-tight">{freeCount}</span>
            <span className="text-[10px] text-zinc-500">ta</span>
          </div>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
        <div className="flex items-center gap-1.5 p-1 bg-zinc-900/90 border border-zinc-800 rounded-xl overflow-x-auto">
          {(
            [
              { id: 'all', label: `Barchasi (${totalCount})` },
              { id: 'contract', label: `Contract (${contractCount})` },
              { id: 'free', label: `Free (${freeCount})` },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setPlanFilter(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors shrink-0 ${
                planFilter === tab.id
                  ? 'bg-zinc-800 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <form onSubmit={handleSearchSubmit} className="relative w-full sm:w-64">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="ID, ism yoki @username..."
            className="w-full pl-8 pr-3 py-2 bg-zinc-900 border border-zinc-800 rounded-xl text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500"
          />
          <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-2.5" />
        </form>
      </div>

      {/* Users List */}
      {loading ? (
        <div className="py-16 text-center text-zinc-500 flex flex-col items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-blue-500 mb-2" />
          <span className="text-xs">Foydalanuvchilar ro‘yxati real-time yuklanmoqda...</span>
        </div>
      ) : users.length === 0 ? (
        <div className="py-12 bg-zinc-900/40 border border-zinc-800/80 rounded-2xl text-center text-zinc-500 text-xs p-6">
          <Users className="w-8 h-8 mx-auto text-zinc-600 mb-2" />
          <span>Foydalanuvchilar topilmadi</span>
        </div>
      ) : (
        <div className="space-y-2.5">
          {users.map((user) => (
            <div
              key={user.user_id}
              onClick={() => openUserDetail(user)}
              className="bg-zinc-900/90 border border-zinc-800 hover:border-zinc-700 rounded-2xl p-3.5 cursor-pointer transition-all flex items-center justify-between gap-3 shadow-sm hover:shadow-md"
            >
              <div className="min-w-0 flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-300 font-bold text-xs shrink-0">
                  {user.first_name ? user.first_name[0].toUpperCase() : 'U'}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-semibold text-white truncate">
                      {user.first_name || 'Foydalanuvchi'}
                    </h4>
                    {user.username && (
                      <span className="text-xs text-blue-400 font-mono">@{user.username}</span>
                    )}
                    <span
                      className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border ${
                        user.plan === 'contract'
                          ? 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30'
                          : 'bg-zinc-800 text-zinc-400 border-zinc-700'
                      }`}
                    >
                      {user.plan}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-zinc-500 mt-0.5 font-mono">
                    <span>ID: {user.user_id}</span>
                    <span>Kanallar: {user.channels_count || 0} ta</span>
                    {user.custom_limit && (
                      <span className="text-indigo-400 font-medium">Limit: {user.custom_limit}/kun</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <span className="text-[11px] text-zinc-500 font-mono hidden sm:inline">
                  {user.created_at ? new Date(user.created_at).toLocaleDateString() : ''}
                </span>
                <ChevronRight className="w-4 h-4 text-zinc-500" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add User Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-t-3xl sm:rounded-2xl w-full max-w-md flex flex-col shadow-2xl overflow-hidden animate-in slide-in-from-bottom duration-200">
            <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <UserPlus className="w-4 h-4 text-blue-400" />
                <h3 className="text-sm font-bold text-white">Yangi Foydalanuvchi Qo‘shish</h3>
              </div>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="p-1.5 text-zinc-400 hover:text-white rounded-xl bg-zinc-900 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="p-4 space-y-3.5 text-xs">
              <div>
                <label className="block text-zinc-400 mb-1 font-medium">
                  Telegram User ID <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  required
                  placeholder="Masalan: 123456789"
                  value={addUserId}
                  onChange={(e) => setAddUserId(e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-xl text-white font-mono text-xs focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-zinc-400 mb-1 font-medium">Ismi</label>
                <input
                  type="text"
                  placeholder="Masalan: Azizbek"
                  value={addFirstName}
                  onChange={(e) => setAddFirstName(e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-xl text-white text-xs focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-zinc-400 mb-1 font-medium">Username (ixtiyoriy)</label>
                <input
                  type="text"
                  placeholder="@username"
                  value={addUsername}
                  onChange={(e) => setAddUsername(e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-xl text-white text-xs focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-zinc-400 mb-1.5 font-medium">Tarif Rejasi</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setAddPlan('free')}
                    className={`p-2.5 rounded-xl border text-left transition-colors ${
                      addPlan === 'free'
                        ? 'bg-zinc-800 border-zinc-600 text-white'
                        : 'bg-zinc-900 border-zinc-800 text-zinc-400'
                    }`}
                  >
                    <span className="font-bold block">Free (Bepul)</span>
                    <span className="text-[10px] text-zinc-500">Maksimal 3 post/kun</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setAddPlan('contract')}
                    className={`p-2.5 rounded-xl border text-left transition-colors ${
                      addPlan === 'contract'
                        ? 'bg-indigo-500/10 border-indigo-500 text-white'
                        : 'bg-zinc-900 border-zinc-800 text-zinc-400'
                    }`}
                  >
                    <span className="font-bold block text-indigo-300">Contract</span>
                    <span className="text-[10px] text-zinc-500">Maxsus limit</span>
                  </button>
                </div>
              </div>

              {addPlan === 'contract' && (
                <div>
                  <label className="block text-zinc-400 mb-1 font-medium">Kunlik Post Limiti</label>
                  <input
                    type="number"
                    min="1"
                    max="500"
                    value={addLimit}
                    onChange={(e) => setAddLimit(parseInt(e.target.value, 10) || 10)}
                    className="w-24 px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-xl text-white font-mono text-xs focus:outline-none focus:border-indigo-500"
                  />
                </div>
              )}

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={addingUser}
                  className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                >
                  {addingUser ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  <span>Foydalanuvchini Saqlash & Xabarnoma Yuborish</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* User Detail & Contract Modal */}
      {selectedUser && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-t-3xl sm:rounded-2xl w-full max-w-md max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-in slide-in-from-bottom duration-200">
            {/* Modal Header */}
            <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white">{selectedUser.first_name}</h3>
                <span className="text-[11px] text-zinc-400 font-mono">
                  Telegram ID: {selectedUser.user_id}
                </span>
              </div>
              <button
                onClick={() => setSelectedUser(null)}
                className="p-1.5 text-zinc-400 hover:text-white rounded-xl bg-zinc-900 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Feedback */}
            {message && (
              <div className="mx-4 mt-3 p-2.5 bg-emerald-950/40 border border-emerald-900/60 rounded-xl text-xs text-emerald-300 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{message}</span>
              </div>
            )}
            {errorMessage && (
              <div className="mx-4 mt-3 p-2.5 bg-red-950/40 border border-red-900/60 rounded-xl text-xs text-red-300 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            {/* Modal Body */}
            <div className="p-4 overflow-y-auto space-y-4 text-xs">
              {/* Plan Choice */}
              <div>
                <label className="block text-zinc-400 mb-1.5 font-medium">Tarif Rejasi</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setPlan('free')}
                    className={`p-3 rounded-xl border text-left transition-colors ${
                      plan === 'free'
                        ? 'bg-zinc-800 border-zinc-600 text-white'
                        : 'bg-zinc-900 border-zinc-800 text-zinc-400'
                    }`}
                  >
                    <span className="font-bold block">Free (Bepul)</span>
                    <span className="text-[10px] text-zinc-500">Maksimal 3 post/kun</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setPlan('contract')}
                    className={`p-3 rounded-xl border text-left transition-colors ${
                      plan === 'contract'
                        ? 'bg-indigo-500/10 border-indigo-500 text-white'
                        : 'bg-zinc-900 border-zinc-800 text-zinc-400'
                    }`}
                  >
                    <span className="font-bold block text-indigo-300">Contract</span>
                    <span className="text-[10px] text-zinc-500">Kengaytirilgan limit</span>
                  </button>
                </div>
              </div>

              {/* Custom Limit if Contract */}
              {plan === 'contract' && (
                <div>
                  <label className="block text-zinc-400 mb-1.5 font-medium">
                    Contract Kunlik Limiti
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min="1"
                      max="500"
                      value={customLimit}
                      onChange={(e) => setCustomLimit(parseInt(e.target.value, 10) || 1)}
                      className="w-24 px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-xl text-white font-mono text-sm focus:outline-none focus:border-indigo-500"
                    />
                    <span className="text-zinc-400">post / kun (har bir kanal uchun)</span>
                  </div>
                  <p className="text-[11px] text-zinc-500 mt-1">
                    Ushbu foydalanuvchiga tegishli barcha kanallarga ushbu limit biriktiriladi.
                  </p>
                </div>
              )}

              {/* Connected Channels List */}
              {selectedUser.channels && selectedUser.channels.length > 0 && (
                <div>
                  <span className="text-zinc-400 font-medium block mb-2">
                    Foydalanuvchining Kanallari ({selectedUser.channels.length} ta)
                  </span>
                  <div className="space-y-1.5">
                    {selectedUser.channels.map((ch) => (
                      <div
                        key={ch.chat_id}
                        className="p-2.5 bg-zinc-900 border border-zinc-800 rounded-xl flex items-center justify-between"
                      >
                        <div className="flex items-center gap-2">
                          <Radio className="w-3.5 h-3.5 text-emerald-400" />
                          <span className="font-medium text-white">{ch.title}</span>
                        </div>
                        <span className="text-[11px] text-zinc-400 font-mono">
                          {ch.daily_limit} post/kun
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Save Button */}
              <button
                onClick={handleSaveContract}
                disabled={saving}
                className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                <span>Tarifni Saqlash</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
