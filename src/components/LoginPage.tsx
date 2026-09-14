import React, { useState, useEffect } from 'react';
import { api, ApiError } from '../api';
import { ShieldCheck, Lock, User, Eye, EyeOff, AlertCircle, Clock, Loader2 } from 'lucide-react';

interface LoginPageProps {
  onLoginSuccess: (user: any) => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess }) => {
  const [userId, setUserId] = useState('8157452043');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [remainingAttempts, setRemainingAttempts] = useState<number | null>(null);
  const [lockoutSeconds, setLockoutSeconds] = useState<number>(0);

  useEffect(() => {
    if (lockoutSeconds <= 0) return;
    const timer = setInterval(() => {
      setLockoutSeconds((prev) => {
        if (prev <= 1) {
          setErrorMessage(null);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [lockoutSeconds]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (lockoutSeconds > 0) return;

    if (!userId.trim() || !password.trim()) {
      setErrorMessage('Telegram ID va parolni kiriting');
      return;
    }

    setLoading(true);
    setErrorMessage(null);

    try {
      const res = await api.login(userId.trim(), password.trim());
      onLoginSuccess(res.user);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message);
        if (err.remainingAttempts !== undefined) {
          setRemainingAttempts(err.remainingAttempts);
        }
        if (err.retryAfter) {
          setLockoutSeconds(err.retryAfter);
        }
      } else {
        setErrorMessage('Tizimga kirishda xatolik yuz berdi');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col justify-center items-center px-4 py-8">
      {/* Container */}
      <div className="w-full max-w-sm">
        {/* Brand Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-zinc-900 border border-zinc-800 text-emerald-400 mb-4 shadow-sm">
            <ShieldCheck className="w-8 h-8" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">AnjurX Super Admin</h1>
          <p className="text-sm text-zinc-400 mt-1">Xavfsiz boshqaruv markazi</p>
        </div>

        {/* Card */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl">
          {/* Lockout Banner */}
          {lockoutSeconds > 0 && (
            <div className="mb-5 p-3.5 bg-red-950/40 border border-red-900/60 rounded-xl flex items-start gap-3 text-red-300">
              <Clock className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
              <div className="text-xs">
                <span className="font-semibold block text-sm text-red-200">Xavfsizlik blokirovkasi</span>
                Juda ko‘p noto‘g‘ri urinishlar. Qaytadan urinish uchun{' '}
                <span className="font-bold text-red-100 font-mono text-sm">{lockoutSeconds}s</span> kuting.
              </div>
            </div>
          )}

          {/* Normal Error Banner */}
          {errorMessage && lockoutSeconds === 0 && (
            <div className="mb-5 p-3.5 bg-red-950/30 border border-red-900/50 rounded-xl flex items-start gap-3 text-red-300">
              <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
              <div className="text-xs">
                <span>{errorMessage}</span>
                {remainingAttempts !== null && remainingAttempts > 0 && (
                  <span className="block mt-1 text-zinc-400">
                    Qolgan urinishlar soni: <strong className="text-zinc-200">{remainingAttempts}</strong>
                  </span>
                )}
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Telegram Numeric ID */}
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5" htmlFor="admin-userid">
                Super Admin Telegram ID
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-zinc-500">
                  <User className="w-4 h-4" />
                </div>
                <input
                  id="admin-userid"
                  type="text"
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  placeholder="Masalan: 8157452043"
                  disabled={loading || lockoutSeconds > 0}
                  className="w-full pl-9 pr-3 py-2.5 bg-zinc-950 border border-zinc-800 rounded-xl text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-emerald-500 transition-colors disabled:opacity-50"
                  required
                />
              </div>
              <p className="text-[11px] text-zinc-500 mt-1">Faqat raqamli Telegram ID qabul qilinadi</p>
            </div>

            {/* Password */}
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5" htmlFor="admin-password">
                Admin Parol / Maxfiy Kalit
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-zinc-500">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  id="admin-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Parolni kiriting..."
                  disabled={loading || lockoutSeconds > 0}
                  className="w-full pl-9 pr-10 py-2.5 bg-zinc-950 border border-zinc-800 rounded-xl text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-emerald-500 transition-colors disabled:opacity-50"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  disabled={loading || lockoutSeconds > 0}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-zinc-500 hover:text-zinc-300 transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading || lockoutSeconds > 0}
              className="w-full mt-2 py-2.5 px-4 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold rounded-xl text-sm flex items-center justify-center gap-2 transition-all shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Tekshirilmoqda...</span>
                </>
              ) : lockoutSeconds > 0 ? (
                <span>Bloklangan ({lockoutSeconds}s)</span>
              ) : (
                <span>Tizimga Kirish</span>
              )}
            </button>
          </form>
        </div>

        {/* Security Notice */}
        <div className="mt-6 text-center text-xs text-zinc-500 flex items-center justify-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-zinc-600" />
          <span>Server-side bruteforce himoyasi faol</span>
        </div>
      </div>
    </div>
  );
};
