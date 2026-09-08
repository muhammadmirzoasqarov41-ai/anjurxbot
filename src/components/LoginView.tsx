import React, { useState, useEffect } from 'react';
import { Shield, Lock, Terminal, CheckCircle2, AlertTriangle, Cpu, Radio, KeyRound } from 'lucide-react';

interface LoginViewProps {
  onLoginSuccess: () => void;
}

export const LoginView: React.FC<LoginViewProps> = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState('usafes');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [accessGranted, setAccessGranted] = useState(false);
  const [cooldownRemaining, setCooldownRemaining] = useState<number | null>(null);

  // Countdown timer for brute force cooldown
  useEffect(() => {
    if (cooldownRemaining === null || cooldownRemaining <= 0) return;
    const timer = setInterval(() => {
      setCooldownRemaining((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(timer);
          setError(null);
          return null;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldownRemaining]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (cooldownRemaining && cooldownRemaining > 0) return;

    setError(null);
    setLoading(true);

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        if (res.status === 429 || data.cooldown_remaining) {
          setCooldownRemaining(data.cooldown_remaining || 30);
          setError(`Brute-force lockout: ${data.cooldown_remaining || 30}s cooldown active.`);
        } else {
          setError(data.error || 'Access Denied: Invalid credentials.');
        }
      } else {
        // Access Granted!
        setAccessGranted(true);
        setTimeout(() => {
          onLoginSuccess();
        }, 900);
      }
    } catch (err: any) {
      setError('Gateway connection error. Ensure server is active.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-cyber-grid flex flex-col items-center justify-center p-4 relative overflow-hidden font-mono-cyber">
      {/* Subtle Neon ambient lights */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-10 left-10 w-64 h-64 bg-emerald-500/5 rounded-full blur-2xl pointer-events-none" />

      {/* Cyber Frame Container */}
      <div
        className={`w-full max-w-md bg-[#080c14] border ${
          accessGranted
            ? 'border-[#00ff66] shadow-[0_0_50px_rgba(0,255,102,0.4)] scale-102'
            : 'border-[#172233] shadow-[0_20px_60px_rgba(0,0,0,0.9)]'
        } rounded-xl p-8 relative transition-all duration-500 z-10`}
      >
        {/* Top Cyber Accent Line */}
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-[#00ff66] to-transparent" />

        {/* Header telemetry badge */}
        <div className="flex items-center justify-between text-[11px] text-slate-500 border-b border-[#152030] pb-3 mb-6 tracking-wider">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#00ff66] animate-pulse shadow-[0_0_8px_#00ff66]" />
            <span className="text-[#00ff66] font-semibold">GATEWAY_ACTIVE</span>
          </div>
          <span className="text-slate-400">TLS 1.3 / HMAC-256</span>
        </div>

        {/* Icon & Title */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-[#0d1522] border border-[#1b2a40] text-[#00ff66] mb-4 shadow-[0_0_20px_rgba(0,255,102,0.15)]">
            {accessGranted ? (
              <CheckCircle2 className="w-7 h-7 text-[#00ff66] animate-bounce" />
            ) : (
              <Shield className="w-7 h-7" />
            )}
          </div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center justify-center gap-2">
            <span>ANJURX_BOT</span>
            <span className="text-xs px-2 py-0.5 rounded bg-[#00ff66]/10 text-[#00ff66] border border-[#00ff66]/30">
              V2.4
            </span>
          </h1>
          <p className="text-xs text-slate-400 mt-1.5 tracking-wide">
            CYBERSECURITY COMMAND & CONTROL CENTER
          </p>
        </div>

        {/* Brute-force Lockout Alert */}
        {cooldownRemaining !== null && cooldownRemaining > 0 && (
          <div className="mb-5 p-3.5 bg-rose-950/40 border border-rose-500/40 rounded-lg text-rose-300 text-xs flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 animate-pulse" />
            <div>
              <div className="font-bold text-rose-200">BRUTE-FORCE LOCKOUT ACTIVE</div>
              <div className="text-[11px] mt-0.5">
                Cooldown remaining:{' '}
                <span className="font-mono text-rose-400 font-bold text-sm">
                  {cooldownRemaining}s
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Error Alert */}
        {error && (!cooldownRemaining || cooldownRemaining <= 0) && (
          <div className="mb-5 p-3 bg-rose-950/30 border border-rose-500/30 rounded-lg text-rose-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Access Granted Animation */}
        {accessGranted && (
          <div className="mb-5 p-3 bg-emerald-950/40 border border-[#00ff66] rounded-lg text-[#00ff66] text-xs flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(0,255,102,0.2)]">
            <CheckCircle2 className="w-4 h-4" />
            <span className="font-bold tracking-wider">ACCESS GRANTED // INITIALIZING...</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
              <Terminal className="w-3.5 h-3.5 text-[#00ff66]" />
              Super Admin Username
            </label>
            <input
              id="admin-username-input"
              type="text"
              required
              disabled={loading || accessGranted}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="usafes"
              className="w-full bg-[#05070d] border border-[#1b283d] rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-[#00ff66] focus:shadow-[0_0_10px_rgba(0,255,102,0.2)] transition-all font-mono"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
              <KeyRound className="w-3.5 h-3.5 text-[#00ff66]" />
              Security Password / Key
            </label>
            <input
              id="admin-password-input"
              type="password"
              required
              disabled={loading || accessGranted || (cooldownRemaining !== null && cooldownRemaining > 0)}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full bg-[#05070d] border border-[#1b283d] rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-[#00ff66] focus:shadow-[0_0_10px_rgba(0,255,102,0.2)] transition-all font-mono"
            />
          </div>

          <button
            id="admin-submit-button"
            type="submit"
            disabled={loading || accessGranted || (cooldownRemaining !== null && cooldownRemaining > 0)}
            className={`w-full py-3 px-4 rounded-lg font-bold text-xs uppercase tracking-widest transition-all duration-200 flex items-center justify-center gap-2 mt-3 cursor-pointer ${
              accessGranted
                ? 'bg-[#00ff66] text-black shadow-[0_0_20px_#00ff66]'
                : cooldownRemaining && cooldownRemaining > 0
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                : 'bg-[#00ff66] hover:bg-[#33ff85] text-black shadow-[0_0_15px_rgba(0,255,102,0.3)] hover:shadow-[0_0_25px_rgba(0,255,102,0.5)] active:scale-[0.99]'
            }`}
          >
            {loading ? (
              <>
                <span className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                <span>VERIFYING PROTOCOL...</span>
              </>
            ) : accessGranted ? (
              <>
                <CheckCircle2 className="w-4 h-4" />
                <span>ACCESS GRANTED</span>
              </>
            ) : cooldownRemaining && cooldownRemaining > 0 ? (
              <span>LOCKED ({cooldownRemaining}s)</span>
            ) : (
              <>
                <Lock className="w-4 h-4" />
                <span>AUTHENTICATE PROTOCOL</span>
              </>
            )}
          </button>
        </form>

        {/* Footer info */}
        <div className="mt-6 pt-4 border-t border-[#152030] flex items-center justify-between text-[10px] text-slate-500">
          <div className="flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-slate-400" />
            <span>PROJECT: anjurxbot</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Radio className="w-3.5 h-3.5 text-[#00ff66]" />
            <span>ID: 8157452043</span>
          </div>
        </div>
      </div>

      <div className="mt-4 text-center text-xs text-slate-600">
        Telegram Group Guard & Anti-Spam Security Protocol &bull; Production
      </div>
    </div>
  );
};
