import React, { useState, useEffect } from 'react';
import { Shield, ShieldAlert, Sliders, Plus, X, Save, CheckCircle2, AlertCircle, Crown, UserCheck, Users, Bot, Info, Search, Sparkles, Trash2 } from 'lucide-react';
import { TelegramGroup, GuardSettings } from '../types';
import { UZBEK_BAD_WORDS, RUSSIAN_BAD_WORDS, ENGLISH_BAD_WORDS, ALL_BAD_WORDS } from '../data/badWords';

interface GuardViewProps {
  groups: TelegramGroup[];
  onUpdateGuard: (groupId: string, guard: GuardSettings) => Promise<void>;
}

export const GuardView: React.FC<GuardViewProps> = ({ groups, onUpdateGuard }) => {
  const [selectedGroupId, setSelectedGroupId] = useState<string>(groups[0]?._id || '');
  const selectedGroup = groups.find((g) => g._id === selectedGroupId) || groups[0];

  const [guard, setGuard] = useState<GuardSettings>(
    selectedGroup?.guard || {
      enabled: true,
      anti_spam: true,
      anti_flood: true,
      anti_link: true,
      anti_ads: true,
      anti_repeat: true,
      bad_words: true,
      new_member_protection: true,
      flood_limit: 5,
      flood_window: 5,
      mute_duration: 300,
      bad_words_list: [],
    }
  );

  const [newBadWord, setNewBadWord] = useState('');
  const [searchBadWord, setSearchBadWord] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    if (selectedGroup) {
      setGuard(selectedGroup.guard);
      setSavedSuccess(false);
    }
  }, [selectedGroupId, selectedGroup]);

  const handleToggle = (key: keyof GuardSettings) => {
    setGuard((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
    setSavedSuccess(false);
  };

  const handleNumberChange = (key: keyof GuardSettings, val: number) => {
    setGuard((prev) => ({
      ...prev,
      [key]: Math.max(1, val),
    }));
    setSavedSuccess(false);
  };

  const handleAddBadWord = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBadWord.trim()) return;
    const splitWords = newBadWord
      .split(/[,;\n]+/)
      .map((w) => w.trim().toLowerCase())
      .filter((w) => w.length >= 2);
    if (splitWords.length > 0) {
      setGuard((prev) => ({
        ...prev,
        bad_words_list: Array.from(new Set([...prev.bad_words_list, ...splitWords])),
      }));
    }
    setNewBadWord('');
    setSavedSuccess(false);
  };

  const handleLoadPreset = (wordsToMerge: string[]) => {
    setGuard((prev) => ({
      ...prev,
      bad_words_list: Array.from(new Set([...prev.bad_words_list, ...wordsToMerge])),
    }));
    setSavedSuccess(false);
  };

  const handleClearBadWords = () => {
    if (window.confirm("Rostdan ham barcha taqiqlangan so'zlarni tozalamoqchimisiz?")) {
      setGuard((prev) => ({
        ...prev,
        bad_words_list: [],
      }));
      setSavedSuccess(false);
    }
  };

  const handleRemoveBadWord = (wordToRemove: string) => {
    setGuard((prev) => ({
      ...prev,
      bad_words_list: prev.bad_words_list.filter((w) => w !== wordToRemove),
    }));
    setSavedSuccess(false);
  };

  const handleSave = async () => {
    if (!selectedGroup) return;
    setIsSaving(true);
    try {
      await onUpdateGuard(selectedGroup._id, guard);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } finally {
      setIsSaving(false);
    }
  };

  if (groups.length === 0) {
    return (
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-8 text-center max-w-xl mx-auto space-y-4">
        <div className="w-16 h-16 rounded-2xl bg-blue-500/10 text-blue-400 flex items-center justify-center mx-auto">
          <Shield className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-white">Hozircha guruhlar ro'yxatga olinmagan</h2>
        <p className="text-slate-400 text-sm leading-relaxed">
          Botni Telegram guruhingizga qo'shing va unga <b>Administrator</b> huquqlarini bering.
          Bot avtomatik tarzda guruh nomi, egasi (owner) va adminlarini aniqlab Firestore bazasiga yozadi!
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-white tracking-tight">🛡️ Qorovul (Guard) Sozlamalari</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Avtomatik filtratsiya
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Guruhdagi xabarlarni tekshirish, spam, havolalar va uyatsiz so'zlarni jazolash qoidalari
          </p>
        </div>

        {/* Group Selector */}
        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-slate-400">Guruhni tanlang:</label>
          <select
            id="select-guard-group"
            value={selectedGroupId}
            onChange={(e) => setSelectedGroupId(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded-xl px-3 py-2 focus:outline-none focus:border-blue-500 font-medium"
          >
            {groups.map((g) => (
              <option key={g._id} value={g._id}>
                {g.title} ({g.members_count} a'zo)
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Selected Group Metadata Card (Owner & Admins Info) */}
      {selectedGroup && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold text-white">{selectedGroup.title}</span>
                {selectedGroup.username && (
                  <span className="text-xs text-blue-400 font-mono">@{selectedGroup.username}</span>
                )}
                <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                  ID: {selectedGroup.group_id}
                </span>
              </div>

              {/* Owner and Admins details */}
              <div className="flex flex-wrap items-center gap-3 mt-3 text-xs text-slate-300">
                {selectedGroup.owner ? (
                  <div className="flex items-center gap-1.5 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 rounded-lg text-amber-300">
                    <Crown className="w-3.5 h-3.5 text-amber-400" />
                    <span>
                      Egasi: <b>{selectedGroup.owner.first_name || 'Guruh Egasi'}</b>
                      {selectedGroup.owner.username && ` (@${selectedGroup.owner.username})`}
                    </span>
                  </div>
                ) : selectedGroup.owner_id ? (
                  <div className="flex items-center gap-1.5 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 rounded-lg text-amber-300">
                    <Crown className="w-3.5 h-3.5 text-amber-400" />
                    <span>Egasi ID: {selectedGroup.owner_id}</span>
                  </div>
                ) : null}

                <div className="flex items-center gap-1.5 bg-blue-500/10 border border-blue-500/20 px-2.5 py-1 rounded-lg text-blue-300">
                  <UserCheck className="w-3.5 h-3.5 text-blue-400" />
                  <span>Adminlar: <b>{selectedGroup.admins?.length || selectedGroup.admin_ids?.length || 1} ta</b></span>
                </div>

                <div className="flex items-center gap-1.5 bg-purple-500/10 border border-purple-500/20 px-2.5 py-1 rounded-lg text-purple-300">
                  <Users className="w-3.5 h-3.5 text-purple-400" />
                  <span>A'zolar: <b>{selectedGroup.members_count.toLocaleString()} ta</b></span>
                </div>

                <div className="flex items-center gap-1.5 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-lg text-emerald-300">
                  <Bot className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Bot holati: <b>{selectedGroup.bot_status || 'administrator'}</b></span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Master Enable/Disable Switch Card */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div
            className={`w-12 h-12 rounded-xl flex items-center justify-center transition-colors ${
              guard.enabled ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-800 text-slate-500'
            }`}
          >
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">Qorovul Tizimi (Master Guard)</h2>
            <p className="text-xs text-slate-400">
              {guard.enabled
                ? "Ushbu guruhda barcha faol filtrlar ishlamoqda"
                : "Qorovul o'chirilgan — xabarlar tekshirilmaydi"}
            </p>
          </div>
        </div>

        <button
          id="btn-toggle-guard-master"
          onClick={() => handleToggle('enabled')}
          className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors focus:outline-none ${
            guard.enabled ? 'bg-emerald-500' : 'bg-slate-700'
          }`}
        >
          <span
            className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${
              guard.enabled ? 'translate-x-6' : 'translate-x-1'
            }`}
          />
        </button>
      </div>

      {/* Guard Rules Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Anti-Spam */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white">Anti-Spam</h3>
            <p className="text-xs text-slate-400 mt-0.5">Haddan tashqari uzun va spam xabarlarni cheklash</p>
          </div>
          <button
            onClick={() => handleToggle('anti_spam')}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              guard.anti_spam ? 'bg-blue-600' : 'bg-slate-700'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                guard.anti_spam ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        {/* Anti-Flood */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white">Anti-Flood</h3>
            <p className="text-xs text-slate-400 mt-0.5">Tez-tez ketma-ket xabar yuborishni taqiqlash</p>
          </div>
          <button
            onClick={() => handleToggle('anti_flood')}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              guard.anti_flood ? 'bg-blue-600' : 'bg-slate-700'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                guard.anti_flood ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        {/* Anti-Link */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white">Anti-Link (Havola filtri)</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              http, https va t.me telegram havolalarini avtomatik o'chirish
            </p>
          </div>
          <button
            onClick={() => handleToggle('anti_link')}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              guard.anti_link ? 'bg-blue-600' : 'bg-slate-700'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                guard.anti_link ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        {/* Anti-Ads */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white">Anti-Ads (Reklama & Qimor)</h3>
            <p className="text-xs text-slate-400 mt-0.5">Stavka, 1xbet, lotereya va kripto reklamalarini to'xtatish</p>
          </div>
          <button
            onClick={() => handleToggle('anti_ads')}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              guard.anti_ads ? 'bg-blue-600' : 'bg-slate-700'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                guard.anti_ads ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        {/* Anti-Repeat */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white">Anti-Repeat (Takrorlash)</h3>
            <p className="text-xs text-slate-400 mt-0.5">Bir xil xabarni qayta-qayta yuborishni bloklash</p>
          </div>
          <button
            onClick={() => handleToggle('anti_repeat')}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              guard.anti_repeat ? 'bg-blue-600' : 'bg-slate-700'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                guard.anti_repeat ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        {/* Bad Words */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white">Bad Words (So'kish va haqorat)</h3>
            <p className="text-xs text-slate-400 mt-0.5">Taqiqlangan so'zlar ro'yxati asosida ogohlantirish</p>
          </div>
          <button
            onClick={() => handleToggle('bad_words')}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              guard.bad_words ? 'bg-blue-600' : 'bg-slate-700'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                guard.bad_words ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Thresholds & Limit Configurations */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Sliders className="w-5 h-5 text-blue-400" />
          <h2 className="text-base font-bold text-white">Cheklov Ko'rsatkichlari (Limits & Timeouts)</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Flood limiti (xabarlar soni)
            </label>
            <input
              type="number"
              min={2}
              max={20}
              value={guard.flood_limit}
              onChange={(e) => handleNumberChange('flood_limit', Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
            />
            <p className="text-[11px] text-slate-500 mt-1">Oyna ichida ruxsat berilgan xabarlar</p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Flood oynasi (soniya)
            </label>
            <input
              type="number"
              min={2}
              max={60}
              value={guard.flood_window}
              onChange={(e) => handleNumberChange('flood_window', Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
            />
            <p className="text-[11px] text-slate-500 mt-1">Tekshiruv oralig'i (standart: 5s)</p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Mute davomiyligi (soniya)
            </label>
            <input
              type="number"
              min={30}
              max={86400}
              value={guard.mute_duration}
              onChange={(e) => handleNumberChange('mute_duration', Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              300 soniya = 5 daqiqa ovozdan mahrum qilish
            </p>
          </div>
        </div>
      </div>

      {/* Bad Words List Editor */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
          <div>
            <h2 className="text-base font-bold text-white mb-0.5">Taqiqlangan So'zlar Lug'ati (Bad Words List)</h2>
            <p className="text-xs text-slate-400">
              Xabarda ushbu so'zlardan biri uchrashi bilanoq avtomatik tarzda o'chiriladi va chora ko'riladi
            </p>
          </div>
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20 self-start sm:self-auto">
            Jami: {guard.bad_words_list.length} ta so'z
          </span>
        </div>

        {/* Quick Presets */}
        <div className="flex flex-wrap items-center gap-2 mb-4 p-3 bg-slate-800/60 rounded-lg border border-slate-800">
          <span className="text-xs text-slate-400 flex items-center gap-1 font-medium">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>Tezkor to'plamlar:</span>
          </span>
          <button
            type="button"
            onClick={() => handleLoadPreset(UZBEK_BAD_WORDS)}
            className="px-2.5 py-1 text-xs rounded-md bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors"
          >
            🇺🇿 O'zbekcha ({UZBEK_BAD_WORDS.length})
          </button>
          <button
            type="button"
            onClick={() => handleLoadPreset(RUSSIAN_BAD_WORDS)}
            className="px-2.5 py-1 text-xs rounded-md bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors"
          >
            🇷🇺 Ruscha ({RUSSIAN_BAD_WORDS.length})
          </button>
          <button
            type="button"
            onClick={() => handleLoadPreset(ENGLISH_BAD_WORDS)}
            className="px-2.5 py-1 text-xs rounded-md bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors"
          >
            🇬🇧 Inglizcha ({ENGLISH_BAD_WORDS.length})
          </button>
          <button
            type="button"
            onClick={() => handleLoadPreset(ALL_BAD_WORDS)}
            className="px-2.5 py-1 text-xs rounded-md bg-blue-600/80 hover:bg-blue-600 text-white font-medium transition-colors"
          >
            ⚡ Barchasini yuklash ({ALL_BAD_WORDS.length})
          </button>
          {guard.bad_words_list.length > 0 && (
            <button
              type="button"
              onClick={handleClearBadWords}
              className="ml-auto px-2 py-1 text-xs rounded-md text-slate-400 hover:text-rose-400 transition-colors flex items-center gap-1"
              title="Ro'yxatni tozalash"
            >
              <Trash2 className="w-3 h-3" />
              <span>Tozalash</span>
            </button>
          )}
        </div>

        {/* Input and Search Controls */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-2 mb-4">
          <form onSubmit={handleAddBadWord} className="md:col-span-8 flex gap-2">
            <input
              id="input-bad-word"
              type="text"
              placeholder="Yangi so'z yoki vergul bilan ajratilgan so'zlar..."
              value={newBadWord}
              onChange={(e) => setNewBadWord(e.target.value)}
              className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 whitespace-nowrap"
            >
              <Plus className="w-4 h-4" />
              <span>Qo'shish</span>
            </button>
          </form>

          <div className="md:col-span-4 relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Ro'yxatdan qidirish..."
              value={searchBadWord}
              onChange={(e) => setSearchBadWord(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        {/* Words Tags Display */}
        <div className="flex flex-wrap gap-1.5 max-h-64 overflow-y-auto pr-1">
          {guard.bad_words_list.length === 0 ? (
            <span className="text-xs text-slate-500 italic py-2">Hozircha taqiqlangan so'zlar kiritilmagan. Yuqoridagi to'plamlardan birini tanlashingiz mumkin.</span>
          ) : (
            guard.bad_words_list
              .filter((word) => !searchBadWord || word.toLowerCase().includes(searchBadWord.toLowerCase()))
              .map((word) => (
                <span
                  key={word}
                  className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-750 text-slate-300 text-xs font-mono border border-slate-700/80"
                >
                  <span>{word}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveBadWord(word)}
                    className="text-slate-500 hover:text-rose-400 transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))
          )}
        </div>
      </div>

      {/* Save Action Footer */}
      <div className="flex items-center justify-between p-4 bg-slate-900 border border-slate-800 rounded-xl">
        <div className="flex items-center gap-2">
          {savedSuccess && (
            <span className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
              <CheckCircle2 className="w-4 h-4" /> Sozlamalar saqlandi!
            </span>
          )}
        </div>

        <button
          id="btn-save-guard"
          onClick={handleSave}
          disabled={isSaving}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-sm font-semibold transition-colors flex items-center gap-2 shadow-lg shadow-blue-500/20"
        >
          <Save className="w-4 h-4" />
          <span>{isSaving ? 'Saqlanmoqda...' : 'O‘zgarishlarni saqlash'}</span>
        </button>
      </div>
    </div>
  );
};
