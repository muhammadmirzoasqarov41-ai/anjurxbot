import React, { useState, useEffect } from 'react';
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

  // Contract form state
  const [plan, setPlan] = useState<'free' | 'contract'>('free');
  const [customLimit, setCustomLimit] = useState<number>(10);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const res = await api.getUsers({ search, plan: planFilter });
      setUsers(res.users || []);
    } catch (err: any) {
      setErrorMessage(err.message || 'Foydalanuvchilarni yuklab bo‘lmadi');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, [planFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadUsers();
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
      setSelectedUser((prev) => prev ? { ...prev, ...res.user } : null);
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

  return (
    <div className="space-y-4 pb-20">
      {/* Header & Search */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <Users className="w-5 h-5 text-blue-400" />
            <span>Foydalanuvchilar va Tariflar</span>
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Jami {users.length} ta ro‘yxatdan o‘tgan foydalanuvchi
          </p>
        </div>

        <form onSubmit={handleSearchSubmit} className="relative w-full sm:w-64">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="ID, ism yoki username..."
            className="w-full pl-8 pr-3 py-2 bg-zinc-900 border border-zinc-800 rounded-xl text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500"
          />
          <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-2.5" />
        </form>
      </div>

      {/* Plan Filters */}
      <div className="flex items-center gap-1.5 p-1 bg-zinc-900/90 border border-zinc-800 rounded-xl overflow-x-auto">
        {(
          [
            { id: 'all', label: 'Barchasi' },
            { id: 'contract', label: 'Contract Tarif' },
            { id: 'free', label: 'Free Tarif' },
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

      {/* Users List */}
      {loading ? (
        <div className="py-16 text-center text-zinc-500 flex flex-col items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-blue-500 mb-2" />
          <span className="text-xs">Foydalanuvchilar yuklanmoqda...</span>
        </div>
      ) : users.length === 0 ? (
        <div className="py-12 bg-zinc-900/40 border border-zinc-800/80 rounded-2xl text-center text-zinc-500 text-xs p-6">
          <Users className="w-8 h-8 mx-auto text-zinc-600 mb-2" />
          <span>Foydalanuvchilar topilmadi</span>
        </div>
      ) : (
        <div className="space-y-3">
          {users.map((user) => (
            <div
              key={user.user_id}
              onClick={() => openUserDetail(user)}
              className="bg-zinc-900/90 border border-zinc-800 hover:border-zinc-700 rounded-2xl p-4 cursor-pointer transition-all flex items-center justify-between gap-3"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-semibold text-white truncate">
                    {user.first_name || 'Foydalanuvchi'}
                  </h4>
                  {user.username && (
                    <span className="text-xs text-zinc-400 font-mono">@{user.username}</span>
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

                <div className="flex items-center gap-3 text-[11px] text-zinc-500 mt-1 font-mono">
                  <span>Telegram ID: {user.user_id}</span>
                  <span>Kanallar: {user.channels_count || 0} ta</span>
                  {user.custom_limit && (
                    <span className="text-indigo-400">Limit: {user.custom_limit}/kun</span>
                  )}
                </div>
              </div>

              <ChevronRight className="w-4 h-4 text-zinc-500 shrink-0" />
            </div>
          ))}
        </div>
      )}

      {/* User Detail & Contract Modal */}
      {selectedUser && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-t-3xl sm:rounded-2xl w-full max-w-md max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-in slide-in-from-bottom duration-200">
            {/* Modal Header */}
            <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white">
                  {selectedUser.first_name}
                </h3>
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
                <label className="block text-zinc-400 mb-1.5 font-medium">
                  Tarif Rejasi
                </label>
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
