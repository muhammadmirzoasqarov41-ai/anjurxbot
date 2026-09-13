import React from 'react';
import { BookOpen, Terminal, Radio, MessageSquare, ShieldCheck, Zap, Download, Upload } from 'lucide-react';

export const GuideView: React.FC = () => {
  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Overview Card */}
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-6">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-orange-500/10 border border-orange-500/20 flex items-center justify-center text-orange-400">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">AnjurX | Rss Bot Qo'llanmasi</h2>
            <p className="text-xs text-zinc-400 mt-0.5">
              Tezkor, ishonchli va resurslarni tejamkor ishlatuvchi Telegram RSS/Atom/JSON Feed o'quvchi
            </p>
          </div>
        </div>
      </div>

      {/* Commands Reference */}
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-6 space-y-4">
        <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center space-x-2">
          <Terminal className="w-4 h-4 text-orange-400" />
          <span>Telegram Bot Buyruqlari</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          <div className="bg-zinc-950/80 border border-zinc-800/80 rounded-lg p-3">
            <div className="font-mono font-bold text-orange-400">/sub &lt;url&gt;</div>
            <p className="text-zinc-300 mt-1">Yangi RSS, Atom yoki JSON feedga obuna bo'lish.</p>
            <div className="text-[11px] text-zinc-500 mt-1">Masalan: <code>/sub https://kun.uz/news/rss</code></div>
          </div>

          <div className="bg-zinc-950/80 border border-zinc-800/80 rounded-lg p-3">
            <div className="font-mono font-bold text-orange-400">/unsub [url]</div>
            <p className="text-zinc-300 mt-1">Obunani bekor qilish. Havolasiz yozilsa, interaktiv tugmali menyu ochiladi.</p>
          </div>

          <div className="bg-zinc-950/80 border border-zinc-800/80 rounded-lg p-3">
            <div className="font-mono font-bold text-orange-400">/rss [raw]</div>
            <p className="text-zinc-300 mt-1">Joriy chatdagi faol obunalar ro'yxatini ko'rish.</p>
            <div className="text-[11px] text-zinc-500 mt-1"><code>/rss raw</code> xom URL manzillarni chiqaradi.</div>
          </div>

          <div className="bg-zinc-950/80 border border-zinc-800/80 rounded-lg p-3">
            <div className="font-mono font-bold text-orange-400">/export</div>
            <p className="text-zinc-300 mt-1">Barcha obunalarni standart .OPML fayl formatida yuklab olish.</p>
          </div>

          <div className="bg-zinc-950/80 border border-zinc-800/80 rounded-lg p-3">
            <div className="font-mono font-bold text-orange-400">/allunsub</div>
            <p className="text-zinc-300 mt-1">Ushbu chatdagi barcha obunalarni tasdiqlash orqali o'chirish.</p>
          </div>

          <div className="bg-zinc-950/80 border border-zinc-800/80 rounded-lg p-3">
            <div className="font-mono font-bold text-orange-400">OPML Fayl Yuborish</div>
            <p className="text-zinc-300 mt-1">Botga .opml yoki .xml faylni hujjat sifatida yuborsangiz, o'nlab feedlarga ommaviy obuna bo'ladi.</p>
          </div>
        </div>
      </div>

      {/* Adding to Channels & Groups */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center space-x-2 text-purple-400">
            <Radio className="w-5 h-5" />
            <h4 className="text-sm font-bold text-white">Telegram Kanallariga Qo'shish</h4>
          </div>
          <ol className="list-decimal list-inside space-y-2 text-xs text-zinc-300 leading-relaxed">
            <li>Kanal sozlamalariga kirib, <b>Administratorlar</b> bo'limini oching.</li>
            <li>Bot username'sini qidiring va <b>Administrator</b> sifatida qo'shing.</li>
            <li>Botga <b>"Xabarlar joylash" (Post Messages)</b> ruxsatini bering.</li>
            <li>Kanalda yoki bot orqali <code>/sub &lt;url&gt;</code> buyrug'ini bering.</li>
          </ol>
        </div>

        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center space-x-2 text-blue-400">
            <MessageSquare className="w-5 h-5" />
            <h4 className="text-sm font-bold text-white">Guruhlarga Qo'shish</h4>
          </div>
          <ol className="list-decimal list-inside space-y-2 text-xs text-zinc-300 leading-relaxed">
            <li>Guruhga botni a'zo sifatida taklif qiling.</li>
            <li>Botni guruhda <b>Administrator</b> qilib tayinlang.</li>
            <li>Faqat guruh administratorlari <code>/sub</code>, <code>/unsub</code> buyruqlaridan foydalana oladi.</li>
            <li>Yangi maqolalar paydo bo'lganda guruhga chiroyli formatda yetkaziladi.</li>
          </ol>
        </div>
      </div>

      {/* Technical Architecture */}
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5 space-y-3">
        <div className="flex items-center space-x-2 text-emerald-400">
          <Zap className="w-5 h-5" />
          <h4 className="text-sm font-bold text-white">Texnik Imkoniyatlar & Xususiyatlar</h4>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
            <span className="font-bold text-white block mb-1">Universal Parser</span>
            <span className="text-zinc-400">RSS 2.0, Atom 1.0, JSON Feed v1 va oddiy veb-sayt linkidan avtomatik feed qidiruv.</span>
          </div>
          <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
            <span className="font-bold text-white block mb-1">Deduplication</span>
            <span className="text-zinc-400">SHA-256 xeshlar orqali eski maqolalar qayta takrorlanmaydi va spam bo'lmaydi.</span>
          </div>
          <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
            <span className="font-bold text-white block mb-1">Gibrid Saqlash</span>
            <span className="text-zinc-400">Firestore Cloud orqali bulutli sinxronizatsiya va lokal JSON tezkor kesh.</span>
          </div>
        </div>
      </div>
    </div>
  );
};
