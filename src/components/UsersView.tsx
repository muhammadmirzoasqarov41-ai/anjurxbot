import React, { useState } from 'react';
import { Users, Search, UserCheck, ShieldAlert, Ban, VolumeX, CheckCircle, RefreshCw, UserPlus } from 'lucide-react';
import { TelegramUser } from '../types';

interface UsersViewProps {
  users: TelegramUser[];
  totalUsers: number;
  page: number;
  totalPages: number;
  onPageChange: (newPage: number) => void;
  onSearch: (query: string) => void;
  onClearWarns: (userId: number) => Promise<void>;
  onAddUser: (user: Partial<TelegramUser>) => Promise<void>;
}

export const UsersView: React.FC<UsersViewProps> = ({
  users,
  totalUsers,
  page,
  totalPages,
  onPageChange,
  onSearch,
  onClearWarns,
  onAddUser,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newUserId, setNewUserId] = useState('');
  const [newUsername, setNewUsername] = useState('');
  const [newFirstName, setNewFirstName] = useState('');
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setSearchTerm(val);
    onSearch(val);
  };

  const handleClear = async (userId: number) => {
    try {
      setActionLoadingId(userId);
      await onClearWarns(userId);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUserId) return;
    await onAddUser({
      user_id: Number(newUserId),
      username: newUsername.replace(/^@/, ''),
      first_name: newFirstName,
    });
    setNewUserId('');
    setNewUsername('');
    setNewFirstName('');
    setIsModalOpen(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-white tracking-tight">👥 Foydalanuvchilar</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
              {totalUsers} ta yozuv
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Guruhlarda qayd qilingan Telegram a'zolari va ularning qoidabuzarlik tarixi
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            id="btn-add-user-modal"
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 px-3.5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition-colors shadow-sm"
          >
            <UserPlus className="w-4 h-4" />
            <span>Foydalanuvchi qo'shish</span>
          </button>
        </div>
      </div>

      {/* Search Input */}
      <div className="relative">
        <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
        <input
          id="input-user-search"
          type="text"
          value={searchTerm}
          onChange={handleSearchChange}
          placeholder="User ID, @username yoki ism bo'yicha qidirish..."
          className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
        />
      </div>

      {/* Main Table */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-800/60 text-slate-300 text-xs font-semibold uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3.5 px-4">User ID</th>
                <th className="py-3.5 px-4">Username</th>
                <th className="py-3.5 px-4">Ism</th>
                <th className="py-3.5 px-4">Qo'shilgan vaqt</th>
                <th className="py-3.5 px-4">Ogohlantirishlar</th>
                <th className="py-3.5 px-4">Holat</th>
                <th className="py-3.5 px-4 text-right">Amallar</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {users.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-400 text-sm">
                    Hech qanday foydalanuvchi topilmadi.
                  </td>
                </tr>
              ) : (
                users.map((user) => {
                  const warns = user.warnings_count ?? 0;
                  const isBanned = user.is_banned;
                  const isMuted = user.is_muted;

                  return (
                    <tr key={user._id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3.5 px-4 font-mono text-xs font-semibold text-slate-300">
                        {user.user_id}
                      </td>
                      <td className="py-3.5 px-4">
                        {user.username ? (
                          <span className="text-blue-400 font-medium">@{user.username}</span>
                        ) : (
                          <span className="text-slate-500">-</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-slate-200 font-medium">
                        {user.first_name || user.last_name ? (
                          `${user.first_name || ''} ${user.last_name || ''}`.trim()
                        ) : (
                          <span className="text-slate-500">-</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-xs text-slate-400 font-mono">
                        {user.created_at || '-'}
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold ${
                              warns >= 3
                                ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                                : warns > 0
                                ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                : 'bg-slate-800 text-slate-400'
                            }`}
                          >
                            {warns} / 3
                          </span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        {isBanned ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                            <Ban className="w-3 h-3" /> Ban
                          </span>
                        ) : isMuted ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            <VolumeX className="w-3 h-3" /> Mute
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            <UserCheck className="w-3 h-3" /> Faol
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        {warns > 0 ? (
                          <button
                            id={`btn-clearwarns-${user.user_id}`}
                            onClick={() => handleClear(user.user_id)}
                            disabled={actionLoadingId === user.user_id}
                            className="px-2.5 py-1 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-lg text-xs font-medium transition-colors"
                          >
                            {actionLoadingId === user.user_id ? 'Tozalanmoqda...' : 'Warn tozalash'}
                          </button>
                        ) : (
                          <span className="text-xs text-slate-500">Toza</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-4 bg-slate-900/90 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <span>
            Sahifa {page} / {totalPages} (Jami {totalUsers} ta)
          </span>
          <div className="flex items-center gap-2">
            <button
              id="btn-prev-page"
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:pointer-events-none rounded-lg text-slate-200 font-medium transition-colors"
            >
              ⬅️ Oldingi
            </button>
            <button
              id="btn-next-page"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:pointer-events-none rounded-lg text-slate-200 font-medium transition-colors"
            >
              Keyingi ➡️
            </button>
          </div>
        </div>
      </div>

      {/* Add User Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl">
            <h2 className="text-lg font-bold text-white mb-1">Yangi foydalanuvchi kiritish</h2>
            <p className="text-xs text-slate-400 mb-4">
              Telegram foydalanuvchisini qo'lda bot ma'lumotlar bazasiga qo'shish
            </p>

            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Telegram User ID *
                </label>
                <input
                  type="number"
                  required
                  placeholder="Masalan: 123456789"
                  value={newUserId}
                  onChange={(e) => setNewUserId(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Username (ixtiyoriy)
                </label>
                <input
                  type="text"
                  placeholder="masalan: alisher_dev"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Ism (ixtiyoriy)
                </label>
                <input
                  type="text"
                  placeholder="Masalan: Alisher"
                  value={newFirstName}
                  onChange={(e) => setNewFirstName(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold transition-colors"
                >
                  Bekor qilish
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition-colors"
                >
                  Saqlash
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
